"""Typed inputs of contexts, document revisions, reviews and file uploads."""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import Field, field_validator

from ..career.models import Input

OwnerType = Literal["knowledge", "template", "document", "context", "job"]


OWNER_COLUMNS = {
    name: f"{name}_id" for name in ["knowledge", "template", "document", "context", "job"]
}


OWNER_TABLES = {
    "knowledge": "knowledge",
    "template": "templates",
    "document": "documents",
    "context": "contexts",
    "job": "jobs",
}


class ContextCreate(Input):
    application_id: str
    template_id: str | None = None
    template_ids: list[str] = Field(default_factory=list, max_length=20)
    knowledge_ids: list[str] | None = Field(default=None, max_length=500)
    claim_ids: list[str] | None = Field(default=None, max_length=1000)
    note: str = Field(default="", max_length=20000)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class DocumentCreate(Input):
    application_id: str
    context_id: str | None = None
    kind: Literal["resume", "cover_letter", "answers", "other"] = "resume"
    title: str = Field(default="", max_length=300)
    content: dict[str, Any] = Field(default_factory=dict)
    previous_id: str | None = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value):
        try:
            encoded = json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ValueError("Content must contain finite JSON values.") from error
        if len(encoded) > 1000000:
            raise ValueError("Structured content exceeds the 1 MB limit.")
        return value


class ReviewUpdate(Input):
    review_state: Literal["approved"] = "approved"
    expected_version: int = Field(ge=1)
    allow_content_mismatch: bool = Field(
        default=False,
        description="Approve although the structured content's text differs from the attached .tex source. Use only for an intentional, reviewed difference.",
    )


StalenessStage = Literal["draft", "applied", "interview", "offer", "closed", "all"]


class UploadReservation(Input):
    owner_type: Literal["knowledge", "template", "document", "job"]
    owner_id: str
    name: str = Field(min_length=1, max_length=500)
    media_type: str = Field(default="application/octet-stream", min_length=1, max_length=200)
    size: int = Field(gt=0, strict=True)
    sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")

    @field_validator("name")
    @classmethod
    def safe_relative_name(cls, value):
        value = value.replace("\\", "/")
        path = PurePosixPath(value)
        if (
            not path.name
            or path.is_absolute()
            or ":" in path.parts[0]
            or any(part in {"..", "."} for part in path.parts)
            or "\x00" in value
        ):
            raise ValueError("Use a relative file name without parent-directory segments.")
        if any(ord(character) < 32 for character in value):
            raise ValueError("Control characters are not permitted in file names.")
        return value

    @field_validator("media_type")
    @classmethod
    def valid_media_type(cls, value):
        if any(ord(character) < 32 or ord(character) > 126 for character in value):
            raise ValueError("Invalid media type.")
        return value
