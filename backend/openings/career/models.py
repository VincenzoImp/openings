"""Typed inputs of the Profile, Career entries, claims, templates and imports, with defaults."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

DEFAULT_PROFILE = {
    "name": "",
    "headline": "",
    "location": "",
    "email": "",
    "phone": "",
    "summary": "",
    "links": [],
    "metadata": {},
}


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("metadata", "rules", "links", check_fields=False)
    @classmethod
    def finite_json(cls, value):
        if value is not None:
            try:
                encoded = json.dumps(value, allow_nan=False)
            except (TypeError, ValueError) as error:
                raise ValueError("Use finite JSON values.") from error
            if len(encoded) > 1000000:
                raise ValueError("Structured metadata exceeds the 1 MB limit.")
        return value


class NonNullUpdate(Input):
    @field_validator("*", mode="before")
    @classmethod
    def reject_null(cls, value, info: ValidationInfo):
        if value is None and info.field_name != "dates":
            raise ValueError(
                "Omit unchanged fields; clear text with an empty string or use an empty list/object."
            )
        return value


class ProfileUpdate(NonNullUpdate):
    expected_version: int = Field(ge=0, strict=True)
    name: str | None = Field(default=None, max_length=200)
    headline: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=300)
    email: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=100)
    summary: str | None = Field(default=None, max_length=20000)
    links: list[dict[str, str]] | None = Field(default=None, max_length=50)
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Free-form extension values. What the owner wants, facts employers ask about and writing rules belong in Preferences.",
    )


KnowledgeKind = Literal[
    "experience",
    "project",
    "course",
    "education",
    "award",
    "publication",
    "fact",
    "skill",
    "language",
    "other",
]


class CareerDates(Input):
    kind: Literal["single", "period"]
    start: str
    end: str | None = None
    current: bool = False

    @field_validator("start", "end")
    @classmethod
    def valid_partial_date(cls, value):
        if value is not None and not re.fullmatch(
            r"(?!0000)[0-9]{4}(?:-(?:0[1-9]|1[0-2]))?", value
        ):
            raise ValueError("Use a year (YYYY) or a year and month (YYYY-MM).")
        return value

    @model_validator(mode="after")
    def valid_period(self):
        if self.kind == "single":
            if self.end is not None or self.current:
                raise ValueError("A single date has no end date or Present flag.")
        elif self.current == (self.end is not None):
            raise ValueError("A period requires either an end date or Present, not both.")
        elif self.end is not None:
            # Compare the known bounds without assigning unknown months to stored dates.
            start_min = self.start if len(self.start) == 7 else self.start + "-01"
            end_max = self.end if len(self.end) == 7 else self.end + "-12"
            if start_min > end_max:
                raise ValueError("The end date precedes the start date.")
        return self


class KnowledgeFields(Input):
    @field_validator("title", "organization", check_fields=False)
    @classmethod
    def clean_header(cls, value, info: ValidationInfo):
        if value is not None:
            value = value.strip()
            if info.field_name == "title" and not value:
                raise ValueError("Entry titles must not be blank.")
        return value

    @field_validator("metadata", check_fields=False)
    @classmethod
    def dedicated_fields(cls, value):
        if value is not None and {"organization", "dates", "skills", "position"} & value.keys():
            raise ValueError("Organization, dates, skills and position have dedicated fields.")
        return value

    @field_validator("skills", check_fields=False)
    @classmethod
    def normalized_skills(cls, value):
        if value is None:
            return value
        result, seen = [], set()
        for skill in value:
            skill = skill.strip()
            if not skill or len(skill) > 200:
                raise ValueError("Use skill names containing 1–200 characters.")
            if skill.casefold() not in seen:
                result.append(skill)
                seen.add(skill.casefold())
        return result


class KnowledgeCreate(KnowledgeFields):
    kind: KnowledgeKind = "experience"
    title: str = Field(min_length=1, max_length=300)
    organization: str = Field(default="", max_length=300)
    dates: CareerDates | None = None
    skills: list[str] = Field(default_factory=list, max_length=200)
    position: int | None = Field(default=None, ge=0, strict=True)
    narrative: str = Field(default="", max_length=100000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Retrying with the same key and request returns the record the first request created.",
    )


class KnowledgeUpdate(KnowledgeFields, NonNullUpdate):
    expected_version: int = Field(ge=1, strict=True)
    kind: KnowledgeKind | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    organization: str | None = Field(default=None, max_length=300)
    dates: CareerDates | None = None
    skills: list[str] | None = Field(default=None, max_length=200)
    position: int | None = Field(default=None, ge=0, strict=True)
    narrative: str | None = Field(default=None, max_length=100000)
    metadata: dict[str, Any] | None = None


# How strongly a claim is preferred when a CV is assembled: core claims carry the
# account, supporting claims are used when the job calls for them, bench claims are
# kept in reserve.
ClaimRole = Literal["core", "supporting", "bench"]
CLAIM_FIELDS = ("default_in_cv", "role", "group")


class ClaimCreate(Input):
    knowledge_id: str
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Retrying with the same key and request returns the record the first request created.",
    )
    text: str = Field(min_length=1, max_length=5000)
    approved: bool = False
    position: int | None = Field(default=None, ge=0, strict=True)
    default_in_cv: bool = Field(
        default=False, description="In the CV unless the job gives a reason to leave it out."
    )
    role: ClaimRole = Field(
        default="supporting",
        description="core carries the account, supporting is used when the job calls for it, bench is kept in reserve.",
    )
    group: str = Field(
        default="", max_length=100, description="A free short name for claims that belong together."
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("group")
    @classmethod
    def trimmed_group(cls, value):
        return value.strip()


class ClaimUpdate(NonNullUpdate):
    expected_version: int = Field(ge=1, strict=True)
    knowledge_id: str | None = None
    text: str | None = Field(default=None, min_length=1, max_length=5000)
    approved: bool | None = None
    position: int | None = Field(default=None, ge=0, strict=True)
    default_in_cv: bool | None = None
    role: ClaimRole | None = None
    group: str | None = Field(default=None, max_length=100)
    metadata: dict[str, Any] | None = None

    @field_validator("group")
    @classmethod
    def trimmed_group(cls, value):
        return value.strip() if value is not None else value


RULES_DESCRIPTION = (
    "Typed limits max_pages, max_bullets and max_bullet_chars; any other key (such as engine "
    "or date_format) is free-form. Writing rules belong in Preferences, not in a template."
)


class TemplateCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["resume", "cover_letter"] = "resume"
    tex: str = Field(default="", max_length=1000000)
    guidance: str = Field(default="", max_length=20000)
    rules: dict[str, Any] = Field(default_factory=dict, description=RULES_DESCRIPTION)
    is_default: bool = False
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Retrying with the same key and request returns the record the first request created.",
    )

    @field_validator("rules")
    @classmethod
    def validate_rules(cls, value):
        return validate_rules(value)


class TemplateUpdate(NonNullUpdate):
    expected_version: int = Field(ge=1, strict=True)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: Literal["resume", "cover_letter"] | None = None
    tex: str | None = Field(default=None, max_length=1000000)
    guidance: str | None = Field(default=None, max_length=20000)
    rules: dict[str, Any] | None = Field(default=None, description=RULES_DESCRIPTION)
    is_default: bool | None = None

    @field_validator("rules")
    @classmethod
    def validate_rules(cls, value):
        return validate_rules(value) if value is not None else None


class ImportPreview(Input):
    text: str = Field(min_length=1, max_length=500000)
    title: str = Field(default="Imported career notes", max_length=300)


class CareerImport(Input):
    knowledge: list[KnowledgeCreate] = Field(default_factory=list, max_length=200)
    profile: dict[str, Any] | None = None
    expected_profile_version: int | None = Field(default=None, ge=0, strict=True)


# The filters, page and detail of each list: MCP's value, REST's query string.
class KnowledgeQuery(Input):
    q: str = ""
    kind: str = ""
    limit: int = 100
    offset: int = 0
    summary: bool = True


class ClaimQuery(Input):
    knowledge_id: str = ""
    approved: bool | None = None
    limit: int = 100
    offset: int = 0
    summary: bool = True
    q: str = ""


class TemplateQuery(Input):
    kind: str = ""
    limit: int = 100
    offset: int = 0
    summary: bool = True
    q: str = ""


def validate_rules(value):
    for key, low, high in [
        ("max_bullet_chars", 20, 5000),
        ("max_bullets", 1, 100),
        ("max_pages", 1, 30),
    ]:
        if key in value and (
            isinstance(value[key], bool)
            or not isinstance(value[key], int)
            or not low <= value[key] <= high
        ):
            raise ValueError(f"{key} must be an integer between {low} and {high}.")
    if "statements" in value:
        raise ValueError(
            "Templates hold no rule statements since 0.24: write them as Writing rules in "
            "Preferences (preferences_update with section writing)."
        )
    return value
