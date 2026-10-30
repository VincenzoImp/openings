"""Local daily slots and intervals, with one durable scheduling cursor per source."""

import re
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator


class IntervalSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["interval"] = "interval"
    minutes: int = Field(default=1440, ge=15, le=43_200)


class DailySchedule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["daily"] = "daily"
    times: list[str] = Field(default_factory=lambda: ["07:00"], min_length=1, max_length=12)
    timezone: str = "UTC"

    @field_validator("times")
    @classmethod
    def valid_times(cls, values):
        if any(not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value) for value in values):
            raise ValueError("Use daily times in HH:MM format.")
        return sorted(set(values))

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Use a valid IANA time zone.") from error
        return value


Schedule = Annotated[IntervalSchedule | DailySchedule, Field(discriminator="kind")]
schedule_adapter = TypeAdapter(Schedule)


def next_due(schedule: dict, last_slot: str | None, moment: datetime | None = None) -> datetime:
    """Return one coalesced overdue slot, or the next future slot.

    Daily slots use the first occurrence of an ambiguous local time. A spring
    clock gap resolves forward through a UTC round trip. Missed slots coalesce
    into the latest elapsed slot instead of building a catch-up queue.
    """
    current = moment or datetime.now(timezone.utc)
    cfg = schedule_adapter.validate_python(schedule or {"kind": "interval"})
    previous = datetime.fromisoformat(last_slot) if last_slot else None
    if cfg.kind == "interval":
        return previous + timedelta(minutes=cfg.minutes) if previous else current
    zone = ZoneInfo(cfg.timezone)
    local = current.astimezone(zone)
    slots = []
    for offset in (-1, 0, 1, 2):
        day = local.date() + timedelta(days=offset)
        for clock in cfg.times:
            hour, minute = map(int, clock.split(":"))
            slot = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone)
            slots.append(slot.astimezone(timezone.utc))
    slots = sorted(set(slots))
    eligible = [slot for slot in slots if previous is None or slot > previous]
    elapsed = [slot for slot in eligible if slot <= current]
    if previous is not None and elapsed:
        return elapsed[-1]
    return next(slot for slot in eligible if slot > current)
