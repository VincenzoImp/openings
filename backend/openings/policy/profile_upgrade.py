"""Schema 13 to 14, the Profile part: ``preferences`` and ``roles`` leave the Profile.

0.19 copied both texts into unconfirmed ``decision`` items and deprecated the
fields; 0.23 removes them. Before they go, each non-empty value must be found
in an item of the policy (``found``): an item's statement, or its text value,
equal to it with runs of whitespace made single spaces, in any section, so an
item the owner moved or reflowed still counts. A value not found (written
after 0.19, or whose item was edited or removed since) is copied, whole and
unchanged, into a new unconfirmed ``decision`` item at the end of the section
(origin ``profile_preferences_removed`` or ``profile_roles_removed``), and the
section's version moves on by one. Then the two keys are removed from the stored
Profile; its other values, its version and its time stay. No event is written,
and frozen contexts keep the Profile they froze.
"""

from __future__ import annotations

import json
import sqlite3

from ..actors import SYSTEM
from ..common import new_id, now

# The removed Profile fields, the label of the item that keeps each one and its origin.
FIELDS = {
    "preferences": ("Preferences", "profile_preferences_removed"),
    "roles": ("Target roles", "profile_roles_removed"),
}


def _plain(text):
    return " ".join(text.split())


def has_value(value):
    """Whether a stored Profile value says anything (0.19 copied the same values)."""
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


def found(conn, value):
    """Whether a policy item already holds the value."""
    for statement, stored in conn.execute("SELECT statement,value FROM policy_items"):
        decoded = json.loads(stored) if stored is not None else None
        if isinstance(value, str):
            texts = [statement] + ([decoded] if isinstance(decoded, str) else [])
            if any(_plain(text) == _plain(value) for text in texts):
                return True
        elif decoded == value:
            return True
    return False


def profile_values(conn):
    """The stored Profile and its non-empty removed fields, as ({...}, {key: value})."""
    row = conn.execute("SELECT data FROM settings WHERE key='profile'").fetchone()
    profile = json.loads(row[0]) if row else None
    if not isinstance(profile, dict):
        return None, {}
    return profile, {key: profile[key] for key in FIELDS if has_value(profile.get(key))}


def migrate(conn):
    """Copy each value no policy item holds, check every value, then remove both fields.

    Returns the keys whose value was found in the policy and those copied.
    """
    profile, values = profile_values(conn)
    result = {"found": [], "copied": []}
    if profile is None:
        return result
    stamp = now()
    for key, value in values.items():
        if found(conn, value):
            result["found"].append(key)
            continue
        label, origin = FIELDS[key]
        position = conn.execute(
            "SELECT coalesce(max(position)+1,0) FROM policy_items WHERE section='decision'"
        ).fetchone()[0]
        text = isinstance(value, str)
        conn.execute(
            "INSERT INTO policy_items(id,section,position,label,statement,value,value_type,"
            "origin,origin_key,created_by_kind,updated_by_kind,created_at,updated_at) "
            "VALUES(?,'decision',?,?,?,?,?,?,?,?,?,?,?)",
            (
                new_id(),
                position,
                label,
                value if text else "",
                # A value that is not text is kept as it was stored.
                None if text else json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                None if text else "structured",
                origin,
                key,
                SYSTEM.kind,
                SYSTEM.kind,
                stamp,
                stamp,
            ),
        )
        conn.execute(
            "UPDATE policy_sections SET version=version+1,updated_at=?,updated_by_kind=?,"
            "updated_by_id=NULL,updated_by_name=NULL,updated_by_token_kind=NULL "
            "WHERE section='decision'",
            (stamp, SYSTEM.kind),
        )
        result["copied"].append(key)
    if not all(found(conn, value) for value in values.values()):
        raise sqlite3.IntegrityError("A Profile preference or role is not in the policy.")
    if any(key in profile for key in FIELDS):
        conn.execute(
            "UPDATE settings SET data=json_remove(data,'$.preferences','$.roles') "
            "WHERE key='profile'"
        )
    return result
