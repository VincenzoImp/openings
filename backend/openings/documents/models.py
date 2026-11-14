"""Typed inputs of document revisions and file uploads."""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from ..career.models import Input

OwnerType = Literal["knowledge", "template", "document", "job"]


OWNER_COLUMNS = {name: f"{name}_id" for name in ["knowledge", "template", "document", "job"]}


OWNER_TABLES = {
    "knowledge": "knowledge",
    "template": "templates",
    "document": "documents",
    "job": "jobs",
}


DocumentKind = Literal["cv", "letter", "answers", "other"]
# A CV or letter revision is its PDF and an optional TeX source; it is complete once
# its PDF is stored. The other kinds keep structured content: there the structure is
# the document (form answers).
SOURCE_KINDS = frozenset({"cv", "letter"})
SHA256 = r"^[a-fA-F0-9]{64}$"
# An inline TeX source, as UTF-8 bytes.
MAX_INLINE_SOURCE = 256 * 1024


def safe_relative_name(value):
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


class FileSpec(Input):
    """A file to upload with a grant the create returns: its name, size and, optionally, hash."""

    name: str = Field(min_length=1, max_length=500)
    size: int = Field(gt=0, strict=True)
    sha256: str | None = Field(default=None, pattern=SHA256)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        return safe_relative_name(value)


class DocumentCreate(Input):
    application_id: str
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Retrying with the same key and request returns the record the first request created.",
    )
    kind: DocumentKind = "cv"
    title: str = Field(default="", max_length=300)
    content: dict[str, Any] | None = Field(
        default=None,
        description="Structured content of form answers or another document. Not accepted for a CV or letter (cv, letter): those are a PDF and an optional TeX source.",
    )
    pdf: FileSpec | None = Field(
        default=None,
        description="CV or letter: the PDF to upload. The result's uploads.pdf is a one-shot grant: PUT the exact bytes to its url with its headers. The revision is incomplete until its PDF is stored, then complete and immutable.",
    )
    source: str | None = Field(
        default=None,
        description="CV or letter, optional: the TeX source inline (UTF-8, at most 256 KB). Its readable text is derived from it; the PDF must then be built from it (the PDF grant names its SHA-256).",
    )
    source_file: FileSpec | None = Field(
        default=None,
        description="CV or letter, optional, instead of source: a .tex file to upload with the grant uploads.source, before the PDF.",
    )
    claim_ids: list[str] = Field(
        default_factory=list,
        max_length=1000,
        description="Approved claims the revision uses.",
    )
    knowledge_ids: list[str] = Field(
        default_factory=list,
        max_length=500,
        description="Career entries the revision uses.",
    )
    note: str = Field(default="", max_length=5000, description="An optional note on the revision.")
    previous_id: str | None = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value):
        if value is None:
            return value
        try:
            encoded = json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ValueError("Content must contain finite JSON values.") from error
        if len(encoded) > 1000000:
            raise ValueError("Structured content exceeds the 1 MB limit.")
        return value

    @field_validator("claim_ids", "knowledge_ids")
    @classmethod
    def distinct_ids(cls, value):
        return list(dict.fromkeys(value))

    @field_validator("source")
    @classmethod
    def bounded_source(cls, value):
        if value is not None and len(value.encode("utf-8")) > MAX_INLINE_SOURCE:
            raise ValueError("An inline source is at most 256 KB; upload a larger one as a file.")
        return value

    @model_validator(mode="after")
    def files_of_a_cv_or_letter(self):
        if self.source is not None and self.source_file is not None:
            raise ValueError(
                "Give the source inline (source) or as a file (source_file), not both."
            )
        if self.kind not in SOURCE_KINDS and (
            self.pdf or self.source is not None or self.source_file
        ):
            raise ValueError("pdf, source and source_file belong to a CV or letter revision.")
        return self


# The filters, page and detail of each list: MCP's value, REST's query string.
class DocumentQuery(Input):
    application_id: str = ""
    kind: str = ""
    limit: int = 100
    offset: int = 0
    summary: bool = True
    q: str = ""


class FileQuery(Input):
    owner_type: OwnerType | None = None
    owner_id: str = ""
    limit: int = 100
    offset: int = 0
    summary: bool = True
    q: str = ""
    media_type: str = ""
    application_id: str = ""


class UploadReservation(Input):
    owner_type: Literal["knowledge", "template", "document", "job"]
    owner_id: str
    name: str = Field(min_length=1, max_length=500)
    media_type: str = Field(default="application/octet-stream", min_length=1, max_length=200)
    size: int = Field(gt=0, strict=True)
    sha256: str | None = Field(default=None, pattern=SHA256)
    source_sha256: str | None = Field(
        default=None,
        pattern=SHA256,
        description="For the PDF of a CV or letter revision that has a TeX source: the SHA-256 of that source (required then; a PDF naming another source is refused). A PDF-only revision names none.",
    )

    @field_validator("name")
    @classmethod
    def safe_relative_name(cls, value):
        return safe_relative_name(value)

    @field_validator("media_type")
    @classmethod
    def valid_media_type(cls, value):
        if any(ord(character) < 32 or ord(character) > 126 for character in value):
            raise ValueError("Invalid media type.")
        return value
