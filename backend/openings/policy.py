"""The owner's policy: short statement lists an agent follows and a context freezes.

Four sections hold items of one shape. ``decision`` has the rules for shortlisting
and dismissing, ``eligibility`` the facts employers ask about, ``writing`` the rules
for documents (each with a scope) and ``facts`` everything else the owner confirmed.
Every section has its own version; an item write names the version of its section.

Confirmation is the owner's. A content write (label, statement, value, scope or
rule) by the dashboard session or an owner token confirms the item; the same write
by an agent token leaves it a proposal and switches its rule off. Only owner
authority confirms a proposal or enables a rule.

A decision item may carry a rule on a collection signal. An enabled rule the owner
confirmed acts on new jobs as their signals arrive (job_signals.py).
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .actors import SYSTEM, column_names, current_actor, pop_actor, require_owner
from .common import encode, new_id, now
from .errors import DomainError, conflict, missing
from .models import Input

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

ORIGIN_NOTES = {
    "profile_metadata": "Copied from Profile metadata in 0.19",
    "profile_preferences": "Copied from Profile preferences in 0.19",
    "profile_roles": "Copied from Profile roles in 0.19",
}
CONTENT_FIELDS = ("label", "statement", "value", "scope", "rule")
_ACTORS = ("created_by", "updated_by", "confirmed_by")

# Mirrored in schema.sql; the 9 -> 10 migration creates the same objects.
SCHEMA = """
CREATE TABLE IF NOT EXISTS policy_sections (
 section TEXT PRIMARY KEY CHECK(section IN ('decision','eligibility','writing','facts')),
 version INTEGER NOT NULL DEFAULT 0, updated_at TEXT,
 updated_by_kind TEXT, updated_by_id TEXT, updated_by_name TEXT, updated_by_token_kind TEXT
);
CREATE TABLE IF NOT EXISTS policy_items (
 id TEXT PRIMARY KEY, section TEXT NOT NULL REFERENCES policy_sections(section),
 position INTEGER NOT NULL DEFAULT 0 CHECK(position>=0),
 label TEXT NOT NULL, statement TEXT NOT NULL DEFAULT '',
 value TEXT CHECK(value IS NULL OR json_valid(value)),
 value_type TEXT CHECK(value_type IS NULL OR value_type IN ('text','number','date','boolean','list','structured')),
 note TEXT NOT NULL DEFAULT '',
 scope TEXT CHECK(scope IS NULL OR scope IN ('cv','letter','all')),
 rule TEXT CHECK(rule IS NULL OR json_valid(rule)),
 enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
 origin TEXT, origin_key TEXT,
 confirmed_at TEXT, confirmed_by_kind TEXT, confirmed_by_id TEXT, confirmed_by_name TEXT, confirmed_by_token_kind TEXT,
 created_by_kind TEXT, created_by_id TEXT, created_by_name TEXT, created_by_token_kind TEXT,
 updated_by_kind TEXT, updated_by_id TEXT, updated_by_name TEXT, updated_by_token_kind TEXT,
 idempotency_key TEXT UNIQUE, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK((value IS NULL)=(value_type IS NULL))
);
CREATE INDEX IF NOT EXISTS policy_items_section ON policy_items(section,position);
INSERT OR IGNORE INTO policy_sections(section) VALUES ('decision'),('eligibility'),('writing'),('facts');
"""


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


def label_from_key(key):
    """A readable label for a Profile metadata key: decision_policy -> Decision policy."""
    text = re.sub(r"[_\-\s]+", " ", str(key)).strip()
    return (text[:1].upper() + text[1:])[:200] or "Untitled"


def item_record(row):
    """A policy item as returned by reads."""
    row = dict(row)
    row["value"] = json.loads(row["value"]) if row["value"] is not None else None
    row["rule"] = json.loads(row["rule"]) if row["rule"] is not None else None
    row["enabled"] = bool(row["enabled"])
    row["confirmed"] = row["confirmed_at"] is not None
    for prefix in _ACTORS:
        actor = pop_actor(row, prefix)
        row[prefix] = None if actor["kind"] == "unknown" else actor
    origin, key = row.pop("origin"), row.pop("origin_key")
    row["origin"] = (
        {"source": origin, "key": key, "note": ORIGIN_NOTES.get(origin, "")} if origin else None
    )
    row.pop("idempotency_key")
    return row


def _items(conn, section):
    return [
        item_record(row)
        for row in conn.execute(
            "SELECT * FROM policy_items WHERE section=? ORDER BY position,created_at,id",
            (section,),
        )
    ]


def _section_row(conn, section):
    row = conn.execute("SELECT * FROM policy_sections WHERE section=?", (section,)).fetchone()
    if row is None:  # a database written by hand; the schema inserts all four
        conn.execute("INSERT INTO policy_sections(section) VALUES(?)", (section,))
        row = conn.execute("SELECT * FROM policy_sections WHERE section=?", (section,)).fetchone()
    return dict(row)


def section_record(conn, section):
    row = _section_row(conn, section)
    actor = pop_actor(row, "updated_by")
    items = _items(conn, section)
    return {
        "section": section,
        "description": SECTION_TITLES[section],
        "version": row["version"],
        "updated_at": row["updated_at"],
        "updated_by": None if actor["kind"] == "unknown" else actor,
        "items": items,
        "total": len(items),
        "unconfirmed": sum(not item["confirmed"] for item in items),
    }


def frozen_policy(conn):
    """The four sections as a context freezes them: version and items.

    Two queries for the whole policy: this runs for every prepared context. An
    item keeps what an agent writes from; an unconfirmed item says so.
    """
    versions = dict(
        tuple(row) for row in conn.execute("SELECT section,version FROM policy_sections")
    )
    frozen = {section: {"version": versions.get(section, 0), "items": []} for section in SECTIONS}
    for row in conn.execute(
        "SELECT section,id,label,statement,value,value_type,note,scope,rule,enabled,"
        "confirmed_at,origin,origin_key FROM policy_items ORDER BY section,position,created_at,id"
    ):
        section, value, rule, confirmed_at, origin = row[0], row[4], row[8], row[10], row[11]
        frozen[section]["items"].append(
            {
                "id": row[1],
                "label": row[2],
                "statement": row[3],
                "value": json.loads(value) if value is not None else None,
                "value_type": row[5],
                "note": row[6],
                "scope": row[7],
                "rule": json.loads(rule) if rule is not None else None,
                "enabled": bool(row[9]),
                "confirmed": confirmed_at is not None,
                "confirmed_at": confirmed_at,
                "origin": {"source": origin, "key": row[12], "note": ORIGIN_NOTES.get(origin, "")}
                if origin
                else None,
            }
        )
    return frozen


def signal_registry():
    return [
        {
            "signal": name,
            "label": signal["label"],
            "description": signal["description"],
            "operators": [
                {"operator": operator, "value_type": kind}
                for operator, kind in signal["operators"].items()
            ],
        }
        for name, signal in SIGNALS.items()
    ]


def _section_name(section):
    if section not in SECTIONS:
        raise DomainError(
            404,
            "not_found",
            "The policy has the sections decision, eligibility, writing and facts.",
        )
    return section


def _check(row, expected):
    if row["version"] != expected:
        conflict(details={"current_version": row["version"], "section": row["section"]})


def _shape(section, scope, rule, enabled):
    """The section-specific fields of an item, or a refusal."""
    if section != "writing" and scope is not None:
        raise DomainError(422, "policy_scope", "Only writing items have a scope.")
    if section != "decision" and rule is not None:
        raise DomainError(422, "policy_rule", "Only decision items carry a signal rule.")
    if enabled and rule is None:
        raise DomainError(422, "policy_rule", "Only an item with a signal rule can be enabled.")
    return ("all" if scope is None else scope) if section == "writing" else None


class PolicyService:
    def __init__(self, workspace):
        self.workspace = workspace
        self.db = workspace.db

    def _event(self, conn, kind, section, version, item_id=None, **payload):
        self.workspace.event(
            kind,
            payload={
                **({"item_id": item_id} if item_id else {}),
                "section": section,
                "version": version,
                **payload,
            },
            conn=conn,
            subject=("policy_item", item_id) if item_id else ("policy", section),
        )

    @staticmethod
    def _bump(conn, section, stamp, *more):
        """One write is one new version of each section it touches."""
        actor = current_actor()
        for name in (section, *more):
            conn.execute(
                "UPDATE policy_sections SET version=version+1,updated_at=?,updated_by_kind=?,updated_by_id=?,updated_by_name=?,updated_by_token_kind=? WHERE section=?",
                (stamp, *actor.columns(), name),
            )

    @staticmethod
    def _item(conn, item_id):
        row = conn.execute("SELECT * FROM policy_items WHERE id=?", (item_id,)).fetchone()
        if row is None:
            missing("Policy item")
        return dict(row)

    @staticmethod
    def _renumber(conn, section, ordered=None):
        if ordered is None:
            ordered = [
                row[0]
                for row in conn.execute(
                    "SELECT id FROM policy_items WHERE section=? ORDER BY position,created_at,id",
                    (section,),
                )
            ]
        conn.executemany(
            "UPDATE policy_items SET position=? WHERE id=?",
            [(position, item_id) for position, item_id in enumerate(ordered)],
        )

    def _result(self, conn, section, item_id=None):
        record = section_record(conn, section)
        item = next((item for item in record["items"] if item["id"] == item_id), None)
        return {"section": record, "item": item}

    def get_policy(self, section: str | None = None) -> dict:
        """Read the owner's policy: every section, or one, with its version and items."""
        with self.db.connect() as conn:
            if section is not None:
                return section_record(conn, _section_name(section))
            return {
                "sections": [section_record(conn, name) for name in SECTIONS],
                "signals": signal_registry(),
                "rule_actions": list(RULE_ACTIONS),
                "signals_applied": SIGNALS_APPLIED,
            }

    def preview_rule(self, value: RulePreview) -> dict:
        """How many jobs to review a rule matches now, with a few examples. Nothing changes.

        Rules act only on new jobs; this shows what the rule would have done to the
        jobs waiting in the Inbox, so the owner can judge it before enabling it.
        """
        value = value if isinstance(value, RulePreview) else RulePreview.model_validate(value)
        return self.workspace.signals.preview(value.rule.model_dump())

    def add_item(self, section: str, value: PolicyItemCreate) -> dict:
        """Add an item to a section. An agent token's item is a proposal until the owner confirms it."""
        section = _section_name(section)
        value = (
            value if isinstance(value, PolicyItemCreate) else PolicyItemCreate.model_validate(value)
        )
        actor = current_actor()
        rule = value.rule.model_dump() if value.rule else None
        scope = _shape(section, value.scope, rule, value.enabled)
        if value.enabled:
            require_owner("enable a policy rule")
        item_id, stamp = new_id(), now()
        confirmed = (None,) * 5 if actor.is_agent else (stamp, *actor.columns())
        with self.db.transaction() as conn:
            if value.idempotency_key:
                old = conn.execute(
                    "SELECT id,section,label FROM policy_items WHERE idempotency_key=?",
                    (value.idempotency_key,),
                ).fetchone()
                if old:
                    if (old["section"], old["label"]) != (section, value.label):
                        conflict("This idempotency key was used for another policy item.")
                    return self._result(conn, section, old["id"])
            row = _section_row(conn, section)
            _check(row, value.expected_version)
            count = conn.execute(
                "SELECT COUNT(*) FROM policy_items WHERE section=?", (section,)
            ).fetchone()[0]
            if count >= 500:
                raise DomainError(422, "policy_limit", "A section holds at most 500 items.")
            position = count if value.position is None else min(value.position, count)
            conn.execute(
                "UPDATE policy_items SET position=position+1 WHERE section=? AND position>=?",
                (section, position),
            )
            conn.execute(
                "INSERT INTO policy_items(id,section,position,label,statement,value,value_type,note,scope,rule,enabled,"
                "confirmed_at,confirmed_by_kind,confirmed_by_id,confirmed_by_name,confirmed_by_token_kind,"
                "created_by_kind,created_by_id,created_by_name,created_by_token_kind,"
                "updated_by_kind,updated_by_id,updated_by_name,updated_by_token_kind,"
                "idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item_id,
                    section,
                    position,
                    value.label,
                    value.statement,
                    encode(value.value) if value.value is not None else None,
                    value.value_type,
                    value.note,
                    scope,
                    encode(rule) if rule else None,
                    int(value.enabled),
                    *confirmed,
                    *actor.columns(),
                    *actor.columns(),
                    value.idempotency_key,
                    stamp,
                    stamp,
                ),
            )
            self._bump(conn, section, stamp)
            self._event(
                conn,
                "policy_item_added",
                section,
                row["version"] + 1,
                item_id,
                confirmed=not actor.is_agent,
            )
            return self._result(conn, section, item_id)

    def update_item(self, item_id: str, value: PolicyItemUpdate) -> dict:
        """Edit an item with its section's version. An agent token's content change makes it a proposal again and switches its rule off."""
        value = (
            value if isinstance(value, PolicyItemUpdate) else PolicyItemUpdate.model_validate(value)
        )
        data = value.model_dump(exclude_unset=True)
        expected = data.pop("expected_version")
        actor = current_actor()
        with self.db.transaction() as conn:
            row = self._item(conn, item_id)
            section = row["section"]
            section_row = _section_row(conn, section)
            _check(section_row, expected)
            previous = {
                "label": row["label"],
                "statement": row["statement"],
                "value": json.loads(row["value"]) if row["value"] is not None else None,
                "value_type": row["value_type"],
                "note": row["note"],
                "scope": row["scope"],
                "rule": json.loads(row["rule"]) if row["rule"] is not None else None,
                "enabled": bool(row["enabled"]),
            }
            merged = {**previous, **data}
            if "value" in data and data["value"] is None:
                merged["value_type"] = None
            if "rule" in data and data["rule"] is None:
                merged["enabled"] = False
            merged["scope"] = _shape(section, merged["scope"], merged["rule"], merged["enabled"])
            changed = [key for key in previous if previous[key] != merged[key]]
            content = [key for key in changed if key in CONTENT_FIELDS or key == "value_type"]
            if content and actor.is_agent:
                merged["enabled"] = False
                changed = [key for key in previous if previous[key] != merged[key]]
            if merged["enabled"] and not previous["enabled"]:
                require_owner("enable a policy rule")
            if not changed:
                return self._result(conn, section, item_id)
            stamp = now()
            if not content:
                confirmed = tuple(
                    row[name] for name in ("confirmed_at", *column_names("confirmed_by"))
                )
            elif actor.is_agent:
                confirmed = (None,) * 5
            else:
                confirmed = (stamp, *actor.columns())
            conn.execute(
                "UPDATE policy_items SET label=?,statement=?,value=?,value_type=?,note=?,scope=?,rule=?,enabled=?,"
                "confirmed_at=?,confirmed_by_kind=?,confirmed_by_id=?,confirmed_by_name=?,confirmed_by_token_kind=?,"
                "updated_by_kind=?,updated_by_id=?,updated_by_name=?,updated_by_token_kind=?,updated_at=? WHERE id=?",
                (
                    merged["label"],
                    merged["statement"],
                    encode(merged["value"]) if merged["value"] is not None else None,
                    merged["value_type"],
                    merged["note"],
                    merged["scope"],
                    encode(merged["rule"]) if merged["rule"] else None,
                    int(merged["enabled"]),
                    *confirmed,
                    *actor.columns(),
                    stamp,
                    item_id,
                ),
            )
            self._bump(conn, section, stamp)
            self._event(
                conn,
                "policy_item_updated",
                section,
                section_row["version"] + 1,
                item_id,
                fields=changed,
                confirmed=confirmed[0] is not None,
            )
            return self._result(conn, section, item_id)

    def confirm_item(self, item_id: str, value: PolicyVersion) -> dict:
        """Confirm an item as it stands. Owner authority: the dashboard session or an owner token."""
        require_owner("confirm a policy item")
        value = value if isinstance(value, PolicyVersion) else PolicyVersion.model_validate(value)
        actor = current_actor()
        with self.db.transaction() as conn:
            row = self._item(conn, item_id)
            section_row = _section_row(conn, row["section"])
            _check(section_row, value.expected_version)
            if row["confirmed_at"] is not None:
                return self._result(conn, row["section"], item_id)
            stamp = now()
            conn.execute(
                "UPDATE policy_items SET confirmed_at=?,confirmed_by_kind=?,confirmed_by_id=?,confirmed_by_name=?,confirmed_by_token_kind=?,updated_at=? WHERE id=?",
                (stamp, *actor.columns(), stamp, item_id),
            )
            self._bump(conn, row["section"], stamp)
            self._event(
                conn, "policy_item_confirmed", row["section"], section_row["version"] + 1, item_id
            )
            return self._result(conn, row["section"], item_id)

    def move_item(self, item_id: str, value: PolicyMove) -> dict:
        """Move an item to the end of another section, with the versions of both. Its confirmation stays."""
        value = value if isinstance(value, PolicyMove) else PolicyMove.model_validate(value)
        actor = current_actor()
        with self.db.transaction() as conn:
            row = self._item(conn, item_id)
            source, target = row["section"], value.section
            source_row, target_row = _section_row(conn, source), _section_row(conn, target)
            _check(source_row, value.expected_version)
            if source == target:
                raise DomainError(422, "policy_move", "The item is already in this section.")
            _check(target_row, value.target_version)
            if row["rule"] is not None:
                raise DomainError(
                    422,
                    "policy_rule",
                    "Remove the signal rule before moving this item out of decision.",
                )
            stamp = now()
            position = conn.execute(
                "SELECT COUNT(*) FROM policy_items WHERE section=?", (target,)
            ).fetchone()[0]
            conn.execute(
                "UPDATE policy_items SET section=?,position=?,scope=?,updated_by_kind=?,updated_by_id=?,updated_by_name=?,updated_by_token_kind=?,updated_at=? WHERE id=?",
                (
                    target,
                    position,
                    "all" if target == "writing" else None,
                    *actor.columns(),
                    stamp,
                    item_id,
                ),
            )
            self._renumber(conn, source)
            self._bump(conn, source, stamp, target)
            self._event(
                conn,
                "policy_item_moved",
                target,
                target_row["version"] + 1,
                item_id,
                from_section=source,
                from_version=source_row["version"] + 1,
            )
            return {**self._result(conn, target, item_id), "from": section_record(conn, source)}

    def reorder_items(self, section: str, value: PolicyReorder) -> dict:
        """Put a section's items in a new order: send every item id of the section once."""
        section = _section_name(section)
        value = value if isinstance(value, PolicyReorder) else PolicyReorder.model_validate(value)
        with self.db.transaction() as conn:
            row = _section_row(conn, section)
            _check(row, value.expected_version)
            current = [item["id"] for item in _items(conn, section)]
            if sorted(current) != sorted(value.item_ids):
                raise DomainError(
                    422,
                    "policy_order",
                    "Send every item id of the section exactly once.",
                    {"item_ids": current},
                )
            if current != value.item_ids:
                stamp = now()
                self._renumber(conn, section, value.item_ids)
                self._bump(conn, section, stamp)
                self._event(conn, "policy_reordered", section, row["version"] + 1)
            return self._result(conn, section)

    def remove_item(self, item_id: str, expected_version: int) -> dict:
        """Permanently remove an item, with its section's version. Frozen contexts keep their copy."""
        with self.db.transaction() as conn:
            row = self._item(conn, item_id)
            section_row = _section_row(conn, row["section"])
            _check(section_row, expected_version)
            conn.execute("DELETE FROM policy_items WHERE id=?", (item_id,))
            self._renumber(conn, row["section"])
            self._bump(conn, row["section"], now())
            self._event(
                conn, "policy_item_removed", row["section"], section_row["version"] + 1, item_id
            )
            return {
                "deleted": True,
                "id": item_id,
                "section": section_record(conn, row["section"]),
            }


def migrate_profile(conn):
    """Schema 9 to 10: create the policy and copy the Profile's free-form values into it.

    Every top-level Profile ``metadata`` key becomes one unconfirmed ``facts`` item
    holding the original value; ``preferences`` and ``roles`` text become one
    unconfirmed ``decision`` item each. The Profile row is not touched.
    """
    # executescript would commit the surrounding upgrade, so run each statement.
    for statement in SCHEMA.split(";\n"):
        if statement.strip():
            conn.execute(statement)
    row = conn.execute("SELECT data,updated_at FROM settings WHERE key='profile'").fetchone()
    if row is None:
        return
    try:
        profile = json.loads(row[0])
    except ValueError:
        return
    if not isinstance(profile, dict):
        return
    stamp = now()
    insert = (
        "INSERT INTO policy_items(id,section,position,label,statement,value,value_type,origin,origin_key,"
        "created_by_kind,updated_by_kind,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)"
    )
    written = set()
    metadata = profile.get("metadata")
    for position, (key, value) in enumerate(metadata.items() if isinstance(metadata, dict) else ()):
        if isinstance(value, bool):
            kind = "boolean"
        elif isinstance(value, (int, float)):
            kind = "number"
        elif isinstance(value, str):
            kind = "text"
        else:
            kind = STRUCTURED
        conn.execute(
            insert,
            (
                new_id(),
                "facts",
                position,
                label_from_key(key),
                "",
                # The original value, in its own key order.
                json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                kind,
                "profile_metadata",
                key,
                SYSTEM.kind,
                SYSTEM.kind,
                stamp,
                stamp,
            ),
        )
        written.add("facts")
    position = 0
    for key, label in (("preferences", "Preferences"), ("roles", "Target roles")):
        text = profile.get(key)
        if isinstance(text, str) and text.strip():
            conn.execute(
                insert,
                (
                    new_id(),
                    "decision",
                    position,
                    label,
                    text,
                    None,
                    None,
                    "profile_" + key,
                    key,
                    SYSTEM.kind,
                    SYSTEM.kind,
                    stamp,
                    stamp,
                ),
            )
            position += 1
            written.add("decision")
    for section in written:
        conn.execute(
            "UPDATE policy_sections SET version=1,updated_at=?,updated_by_kind=? WHERE section=?",
            (stamp, SYSTEM.kind, section),
        )


def register_api(router, policy: PolicyService):
    @router.get("/policy")
    def policy_get():
        return policy.get_policy()

    @router.get("/policy/{section}")
    def policy_get_section(section: Section):
        return policy.get_policy(section)

    @router.post("/policy/rules/preview")
    def policy_rule_preview(value: RulePreview):
        return policy.preview_rule(value)

    @router.post("/policy/{section}/items", status_code=201)
    def policy_add(section: Section, value: PolicyItemCreate):
        return policy.add_item(section, value)

    @router.post("/policy/{section}/reorder")
    def policy_reorder(section: Section, value: PolicyReorder):
        return policy.reorder_items(section, value)

    @router.patch("/policy/items/{item_id}")
    def policy_update(item_id: str, value: PolicyItemUpdate):
        return policy.update_item(item_id, value)

    @router.post("/policy/items/{item_id}/confirm")
    def policy_confirm(item_id: str, value: PolicyVersion):
        return policy.confirm_item(item_id, value)

    @router.post("/policy/items/{item_id}/move")
    def policy_move(item_id: str, value: PolicyMove):
        return policy.move_item(item_id, value)

    @router.delete("/policy/items/{item_id}")
    def policy_remove(item_id: str, expected_version: int):
        return policy.remove_item(item_id, expected_version)


def register_mcp(mcp, policy: PolicyService):
    from mcp.types import ToolAnnotations

    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    write = ToolAnnotations(destructiveHint=False, openWorldHint=False)
    remove = ToolAnnotations(destructiveHint=True, openWorldHint=False)

    @mcp.tool(annotations=read)
    def policy_get(section: Section | None = None) -> dict:
        """Read the owner's policy: the sections decision (rules for shortlisting and dismissing), eligibility (facts employers ask about), writing (document rules with scope cv, letter or all) and facts, each with its own version and items. Omit section for all four plus the signal registry. An item with confirmed=false is a proposal or a value copied from the old Profile: do not rely on it; ask the owner to confirm it."""
        return policy.get_policy(section)

    @mcp.tool(annotations=read)
    def policy_rule_preview(value: RulePreview) -> dict:
        """Dry run of a decision rule: how many jobs waiting in the Inbox it matches now (matches), how many have no signals yet (pending), out of inbox, with up to five examples. Nothing is dismissed: an enabled rule the owner confirmed acts only on new jobs. Use it before proposing a rule."""
        return policy.preview_rule(value)

    @mcp.tool(annotations=write)
    def policy_add(section: Section, value: PolicyItemCreate) -> dict:
        """Add a policy item with the section's current version: a short label, the statement in the owner's words, an optional typed value and note. An agent token's item is a proposal until the owner confirms it (policy_confirm is owner only). Use an idempotency key for retries."""
        return policy.add_item(section, value)

    @mcp.tool(annotations=write)
    def policy_update(item_id: str, value: PolicyItemUpdate) -> dict:
        """Edit a policy item with its section's current version; omitted fields stay, and value, scope or rule accept null to clear. A content change by an agent token makes the item a proposal again and switches its rule off; enabling a rule needs owner authority."""
        return policy.update_item(item_id, value)

    @mcp.tool(annotations=write)
    def policy_move(item_id: str, value: PolicyMove) -> dict:
        """Move a policy item to the end of another section, with the current versions of both sections; use it to sort items copied from the old Profile out of facts. Its confirmation stays."""
        return policy.move_item(item_id, value)

    @mcp.tool(annotations=write)
    def policy_reorder(section: Section, value: PolicyReorder) -> dict:
        """Put a section's items in a new order, with the section's current version: item_ids lists every item id of the section once."""
        return policy.reorder_items(section, value)

    @mcp.tool(annotations=write)
    def policy_confirm(item_id: str, value: PolicyVersion) -> dict:
        """Confirm a proposed policy item as it stands, with its section's current version. Owner only: an agent token is refused with forbidden and asks the owner instead."""
        return policy.confirm_item(item_id, value)

    @mcp.tool(annotations=remove)
    def policy_remove(item_id: str, expected_version: int) -> dict:
        """Permanently remove a policy item, with its section's current version. Contexts already prepared keep their frozen copy."""
        return policy.remove_item(item_id, expected_version)
