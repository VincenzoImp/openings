"""Policy sections, the signal registry and the typed inputs of items and rules."""

from __future__ import annotations

import math
import re
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from ..models import Input

Section = Literal["decision", "eligibility", "writing", "facts"]


SECTIONS = ("decision", "eligibility", "writing", "facts")


SECTION_TITLES = {
    "decision": "Rules for shortlisting and dismissing jobs",
    "eligibility": "Facts employers ask about",
    "writing": "Rules for your documents",
    "facts": "Other things you have confirmed",
}


Scope = Literal["cv", "letter", "all"]


ValueType = Literal["text", "number", "date", "boolean", "list"]


# A value copied from Profile metadata that is not a scalar. It is read-only: an
# update may replace it with a typed value or clear it, never write another one.
STRUCTURED = "structured"


# Collection signals a decision rule may name, with the comparisons each allows
# and the type of the compared value. job_signals.py computes them and applies rules.
SIGNALS = {
    "language_required": {
        "label": "Required language",
        "description": "Languages the posting text requires.",
        "operators": {"in": "list", "not_in": "list"},
    },
    "posting_language": {
        "label": "Posting language",
        "description": "The language the posting is written in.",
        "operators": {"in": "list", "not_in": "list"},
    },
    "likely_duplicate": {
        "label": "Likely duplicate",
        "description": "Confidence, from 0 to 1, that the posting repeats an existing job.",
        "operators": {"at_least": "number"},
    },
    "no_longer_listed": {
        "label": "No longer listed",
        "description": "The source stopped listing the posting.",
        "operators": {"is": "boolean"},
    },
}


RULE_ACTIONS = ("dismiss", "flag")


SIGNALS_APPLIED = True


CONTENT_FIELDS = ("label", "statement", "value", "scope", "rule")


def _typed_value(value, value_type):
    """Check a small typed value and return it with its type."""
    if value_type is None:
        if isinstance(value, bool):
            value_type = "boolean"
        elif isinstance(value, (int, float)):
            value_type = "number"
        elif isinstance(value, str):
            value_type = "text"
        elif isinstance(value, list):
            value_type = "list"
        else:
            raise ValueError("Use text, a number, a date, true/false or a short list of texts.")
    if value_type == "text":
        if not isinstance(value, str) or not value.strip() or len(value) > 2000:
            raise ValueError("A text value has 1–2000 characters.")
        value = value.strip()
    elif value_type == "number":
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError("A number value is a finite number.")
    elif value_type == "date":
        if not isinstance(value, str) or not re.fullmatch(
            r"[0-9]{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12][0-9]|3[01]))?)?", value
        ):
            raise ValueError("A date value is YYYY, YYYY-MM or YYYY-MM-DD.")
    elif value_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError("A boolean value is true or false.")
    else:
        if (
            not isinstance(value, list)
            or not 1 <= len(value) <= 50
            or any(
                not isinstance(item, str) or not item.strip() or len(item) > 200 for item in value
            )
        ):
            raise ValueError("A list value has 1–50 texts of at most 200 characters.")
        value = [item.strip() for item in value]
    return value, value_type


class RuleCondition(Input):
    operator: Literal["in", "not_in", "at_least", "is"]
    value: Any


class PolicyRule(Input):
    """A machine-readable rule on a collection signal, applied to new jobs while enabled and confirmed."""

    signal: Literal["language_required", "posting_language", "likely_duplicate", "no_longer_listed"]
    condition: RuleCondition
    action: Literal["dismiss", "flag"]

    @model_validator(mode="after")
    def matches_signal(self):
        operators = SIGNALS[self.signal]["operators"]
        expected = operators.get(self.condition.operator)
        if expected is None:
            raise ValueError(
                f"The signal {self.signal} allows the operators: {', '.join(sorted(operators))}."
            )
        value, _ = _typed_value(self.condition.value, expected)
        if self.signal == "likely_duplicate" and not 0 <= value <= 1:
            raise ValueError("A duplicate confidence is between 0 and 1.")
        self.condition.value = value
        return self


class ItemFields(Input):
    @field_validator("label", "statement", "note", check_fields=False)
    @classmethod
    def trimmed(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("label", check_fields=False)
    @classmethod
    def named(cls, value):
        if value is not None and not value:
            raise ValueError("Give the item a short label.")
        return value

    @model_validator(mode="after")
    def typed_value(self):
        value = getattr(self, "value", None)
        value_type = getattr(self, "value_type", None)
        if value is None:
            if value_type is not None:
                raise ValueError("value_type needs a value.")
        else:
            self.value, self.value_type = _typed_value(value, value_type)
        return self


class PolicyItemCreate(ItemFields):
    expected_version: int = Field(ge=0, strict=True, description="The section's current version.")
    label: str = Field(min_length=1, max_length=200)
    statement: str = Field(default="", max_length=10000)
    value: Any | None = Field(
        default=None,
        description="Optional typed value: text, a number, a date, true/false or a short list of texts.",
    )
    value_type: ValueType | None = Field(
        default=None, description="Inferred from the value when omitted; name date explicitly."
    )
    note: str = Field(default="", max_length=4000)
    scope: Scope | None = Field(
        default=None, description="Writing items only: cv, letter or all (the default)."
    )
    rule: PolicyRule | None = Field(
        default=None,
        description="Decision items only: {signal, condition: {operator, value}, action}. While enabled and confirmed by the owner, it acts on each new job as its signals arrive: dismiss (attributed to the rule, restorable) or flag.",
    )
    enabled: bool = Field(
        default=False,
        description="Whether the rule may be applied automatically. Owner authority only.",
    )
    position: int | None = Field(default=None, ge=0, strict=True)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class PolicyItemUpdate(ItemFields):
    """Omitted fields stay. value, scope and rule accept null to clear them."""

    expected_version: int = Field(ge=0, strict=True, description="The section's current version.")
    label: str | None = Field(default=None, min_length=1, max_length=200)
    statement: str | None = Field(default=None, max_length=10000)
    value: Any | None = None
    value_type: ValueType | None = None
    note: str | None = Field(default=None, max_length=4000)
    scope: Scope | None = None
    rule: PolicyRule | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def no_null_text(self):
        for name in ("label", "statement", "note", "enabled"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"Omit {name} to keep it; clear text with an empty string.")
        return self


class PolicyVersion(Input):
    expected_version: int = Field(ge=0, strict=True, description="The section's current version.")


class PolicyMove(Input):
    expected_version: int = Field(
        ge=0, strict=True, description="Current version of the item's section."
    )
    section: Section = Field(description="The section the item moves to.")
    target_version: int = Field(
        ge=0, strict=True, description="Current version of the section it moves to."
    )


class RulePreview(Input):
    rule: PolicyRule = Field(
        description="The rule to try: {signal, condition: {operator, value}, action}; it need not be saved."
    )


class PolicyReorder(Input):
    expected_version: int = Field(ge=0, strict=True, description="The section's current version.")
    item_ids: list[str] = Field(
        max_length=500, description="Every item id of the section, in the new order."
    )
