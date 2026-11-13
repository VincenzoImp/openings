"""PolicyService: item writes with section versions, owner confirmation and rule preview."""

from __future__ import annotations

import json

from ..actors import column_names, current_actor, require_owner
from ..common import encode, new_id, now
from ..errors import DomainError, conflict, missing
from .models import (
    CONTENT_FIELDS,
    RULE_ACTIONS,
    SECTIONS,
    SIGNALS_APPLIED,
    PolicyItemCreate,
    PolicyItemUpdate,
    PolicyMove,
    PolicyReorder,
    PolicyVersion,
    RulePreview,
)
from .records import (
    _check,
    _items,
    _section_name,
    _section_row,
    _shape,
    section_record,
    signal_registry,
)


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
