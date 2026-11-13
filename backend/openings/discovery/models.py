"""Typed inputs of collection sources, runs and bulk source changes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..collectors.catalog import COMPANY_KINDS
from ..scheduling import IntervalSchedule, Schedule

SourceKind = Literal["auto", "jobspy", "rss", *COMPANY_KINDS]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Filters(Input):
    titles: list[str] = Field(default_factory=list, max_length=30)
    locations: list[str] = Field(default_factory=list, max_length=30)
    exclude_titles: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("titles", "locations", "exclude_titles")
    @classmethod
    def clean_terms(cls, values):
        return list(dict.fromkeys(v.strip()[:150] for v in values if v.strip()))


class SourcePreview(Input):
    name: str = Field(default="", max_length=200)
    url: str = Field(default="", max_length=2000)
    kind: SourceKind = "auto"
    config: dict[str, Any] = Field(default_factory=dict)
    filters: Filters = Field(default_factory=Filters)


class SourceCreate(SourcePreview):
    enabled: bool = False
    schedule: Schedule = Field(default_factory=IntervalSchedule)


class RSSConfig(Input):
    url: str = Field(min_length=1, max_length=2000)
    max_results: int = Field(default=100, ge=1, le=2000)


class SourcePatch(Input):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=2000)
    kind: SourceKind | None = None
    config: dict[str, Any] | None = None
    filters: Filters | None = None
    enabled: bool | None = None
    schedule: Schedule | None = None

    @model_validator(mode="after")
    def reject_null(self):
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Source fields cannot be null; omit unchanged fields.")
        return self


class CollectionWrite(Input):
    enabled: bool
    expected_version: int = Field(ge=0)


class SourceVersion(Input):
    id: str
    expected_version: int = Field(ge=1)


class RunOverrides(Input):
    hours_old: int | None = Field(default=None, ge=1, le=8760)
    results_wanted: int | None = Field(default=None, ge=1, le=50)
    max_results: int | None = Field(default=None, ge=1, le=2000)

    @model_validator(mode="after")
    def reject_null(self):
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Omit unchanged run options rather than sending null.")
        return self


class SourceRun(Input):
    expected_version: int = Field(ge=1)
    overrides: RunOverrides = Field(default_factory=RunOverrides)


class SourceConfigure(Input):
    schedule: Schedule | None = None
    config: dict[str, Any] | None = None
    filters: Filters | None = None

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Provide at least one non-null configuration field.")
        return self


class SourceBulk(Input):
    action: Literal["enable", "pause", "run", "delete", "configure"]
    items: list[SourceVersion] = Field(min_length=1, max_length=200)
    patch: SourceConfigure | None = None
    overrides: RunOverrides = Field(default_factory=RunOverrides)

    @model_validator(mode="after")
    def valid_options(self):
        if (self.action == "configure") != (self.patch is not None):
            raise ValueError("A configuration patch is required only for Configure.")
        if self.action != "run" and self.overrides.model_fields_set:
            raise ValueError("Run overrides apply only to Run.")
        if len({item.id for item in self.items}) != len(self.items):
            raise ValueError("Select each source once.")
        return self
