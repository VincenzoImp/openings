"""Career entries and highlights in batches, and one save for templates.

``read_career`` returns whole entries with their highlights and files. A save item
with an id updates that record (its ``expected_version`` is required); without one
it creates a record (``idempotency_key`` makes a retry return it). Each item is
validated against the create or update model and applied on its own.
"""

from __future__ import annotations

from pydantic import ValidationError

from ..common import run_items
from ..errors import DomainError, invalid
from .models import (
    CareerRead,
    CareerSave,
    ClaimCreate,
    ClaimUpdate,
    HighlightsSave,
    KnowledgeCreate,
    KnowledgeUpdate,
    TemplateCreate,
    TemplateSave,
    TemplateUpdate,
)


def _version_required(identifier, version, what):
    if identifier is not None and version is None:
        raise DomainError(
            422,
            "validation",
            "Some fields need attention.",
            [
                {
                    "field": ["expected_version"],
                    "message": f"Updating a {what} needs its version.",
                    "type": "missing",
                }
            ],
        )


def _split(item, identifier_field):
    """The item's identifier and the fields for the create or update model."""
    data = item.model_dump(exclude_unset=True, exclude={identifier_field})
    identifier = getattr(item, identifier_field)
    if identifier is not None:
        if "idempotency_key" in data:
            raise DomainError(
                422, "idempotency_key", "An idempotency_key goes with a new record only."
            )
    else:
        data.pop("expected_version", None)
    return identifier, data


def _echo(record, *keys):
    return {key: record.get(key) for key in ("id", "version", *keys)}


class CareerBatches:
    """career_get, career_save, highlights_save and templates_save."""

    def read_career(self, value: CareerRead) -> dict:
        if value.ids:
            identifiers, unknown = list(dict.fromkeys(value.ids)), []
        else:
            page = self.list_knowledge(q=value.q, kind=value.kind, limit=50, summary=True)
            identifiers, unknown = [item["id"] for item in page["items"]], []
        items = []
        files = self.workspace.documents
        for identifier in identifiers:
            try:
                entry = self.get_knowledge(identifier)
            except DomainError as error:
                if error.status != 404:
                    raise
                unknown.append(identifier)
                continue
            entry["highlights"] = self.list_claims(career_id=identifier, limit=200, summary=False)[
                "items"
            ]
            for highlight in entry["highlights"]:
                highlight.pop("career_id", None)
            entry["files"] = files.list_files(owner_type="career", owner_id=identifier)["items"]
            items.append(entry)
        return {"items": items, "missing": unknown}

    def save_career(self, value: CareerSave) -> dict:
        def apply(item):
            identifier, data = _split(item, "career_id")
            _version_required(identifier, item.expected_version, "career entry")
            if identifier is None:
                record = self.create_knowledge(KnowledgeCreate.model_validate(data))
            else:
                record = self.update_knowledge(identifier, KnowledgeUpdate.model_validate(data))
            return _echo(record, "title")

        return run_items(self.db, value.items, lambda item: item.career_id, apply)

    def save_highlights(self, value: HighlightsSave) -> dict:
        def apply(item):
            identifier, data = _split(item, "highlight_id")
            _version_required(identifier, item.expected_version, "highlight")
            if identifier is None:
                record = self.create_claim(ClaimCreate.model_validate(data))
            else:
                record = self.update_claim(identifier, ClaimUpdate.model_validate(data))
            return _echo(record, "career_id", "approved", "always_include")

        return run_items(self.db, value.items, lambda item: item.highlight_id, apply)

    def save_template(self, value: TemplateSave) -> dict:
        identifier, data = _split(value, "template_id")
        _version_required(identifier, value.expected_version, "template")
        try:
            if identifier is None:
                return self.create_template(TemplateCreate.model_validate(data))
            return self.update_template(identifier, TemplateUpdate.model_validate(data))
        except ValidationError as error:
            raise invalid(error) from error
