"""Typed inputs of collection sources, runs and bulk source changes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..collectors.catalog import COMPANY_KINDS
from ..collectors.policy import ProviderPatch
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
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="A retry with the same key returns the first result.",
    )


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


class ProviderUpdate(ProviderPatch):
    clear_cooldown: bool = Field(
        default=False,
        description="true lifts a pause the provider asked for (Retry-After) now.",
    )

    def patch(self):
        """The policy change, without the cooldown switch."""
        fields = self.model_dump(exclude_unset=True, exclude={"clear_cooldown", "provider_id"})
        return ProviderPatch(**fields)


class ProviderChange(ProviderUpdate):
    provider_id: str = Field(min_length=1, max_length=100)


class CollectionWrite(Input):
    """The collection switch with its version; also provider limits and fetches to stop
    or retry (each applied on its own, results in ``results``)."""

    expected_version: int = Field(ge=0, description="The collection's version.")
    enabled: bool | None = Field(default=None, description="Scheduled collection on or off.")
    providers: list[ProviderChange] = Field(
        default_factory=list,
        max_length=50,
        description="Provider limits, each with its own expected_version.",
    )
    cancel: list[str] = Field(
        default_factory=list, max_length=200, description="Fetch (task) or run ids to stop."
    )
    retry: list[str] = Field(
        default_factory=list, max_length=200, description="Failed or cancelled fetch ids."
    )


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


class SourceItem(Input):
    """A source to create (no source_id) or update (source_id and expected_version)."""

    source_id: str | None = Field(default=None, description="Update this source; omit to add.")
    expected_version: int | None = Field(default=None, ge=1, description="Required to update.")
    name: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=2000)
    kind: SourceKind | None = None
    config: dict[str, Any] | None = None
    filters: Filters | None = None
    enabled: bool | None = Field(default=None, description="false pauses it.")
    schedule: Schedule | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class SourcesSave(Input):
    items: list[SourceItem] = Field(min_length=1, max_length=50)


class SourceRunInput(Input):
    """Fetch a saved source now, or preview a saved or unsaved one without storing jobs."""

    source_id: str | None = Field(default=None, description="The saved source.")
    expected_version: int | None = Field(
        default=None, ge=1, description="Required to fetch a saved source."
    )
    preview: bool = Field(
        default=False, description="true: up to 20 postings it would collect, nothing stored."
    )
    name: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=2000)
    kind: SourceKind | None = None
    config: dict[str, Any] | None = None
    filters: Filters | None = None
    overrides: RunOverrides | None = None


class Query(BaseModel):
    """The filters and page of a list: MCP's value, REST's query string (not strict)."""

    model_config = ConfigDict(extra="forbid")


class CollectionRunQuery(Query):
    limit: int = 50
    offset: int = 0
    source_id: str | None = None
    state: str | None = None
    summary: bool = True


class SourceQuery(Query):
    limit: int = Field(default=100, ge=1)
    offset: int = Field(default=0, ge=0)
    summary: bool = True


class CollectionQuery(Query):
    include: list[Literal["kinds", "providers", "fetches"]] = Field(
        default_factory=list,
        description="kinds: source kinds and their config fields; providers: limits and "
        "cooldowns; fetches: active and failed fetches.",
    )


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
