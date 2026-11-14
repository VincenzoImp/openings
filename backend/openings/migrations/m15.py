"""Schema 14 (0.23) to schema 15 (0.24): a new file with the workspace copied in.

The workspace is not changed in place. A new file, ``<db>.next``, is created from
``schema.sql`` (the same script that creates a new workspace), the schema-14 file
is attached read-only and every kept table is copied with one ``INSERT ... SELECT``
in one transaction. Values that leave the schema go to a JSON archive beside the
database. After the checks below the original file becomes the pre-upgrade copy
and the new file takes its name, so an upgraded workspace has exactly the objects
of a new one and the original is never written.

``upgrade(path)``, at startup:

1. Room: the volume needs ``ROOM_FACTOR`` times the database plus the estimated
   archive; otherwise the start is refused and nothing is written.
2. ``wal_checkpoint(TRUNCATE)`` on the original; ``<db>.next`` from ``schema.sql``;
   the original attached read-only as ``old``.
3. One transaction: each table of ``TABLES`` in order, then ``FOLDS``, then a
   rebuild of the search index.
4. The archive ``<stem>.pre-0.24-archive.json``: written to a temporary name,
   mode 0600, renamed.
5. Checks: ``integrity_check``, no broken reference the original did not have,
   row counts (copied plus created by folds), ``INVARIANTS`` and the archive read
   back with the counts of its sources. Any failure removes the new file and the
   archive and refuses the start with the reason.
6. Swap: the original becomes ``<stem>.pre-0.24.sqlite``, the new file takes the
   database's name, the directory is flushed and both paths are logged.
7. ``recover(path)`` at the next start finishes an interrupted swap or removes an
   unfinished new file (the upgrade then runs again).

``convert(source, target, archive)`` is steps 2 to 5 for a copy (restoring an
uploaded schema-14 backup): the source file is only read.

This module is frozen with its release: it imports only the standard library and
holds every statement and column map it needs. Until 0.24 is released, the issues
of that release extend it ("edit the unreleased migration"): a changed table gets
a ``Table`` entry with its ``columns`` expressions, removed records get a
``Section`` of the archive, rows the upgrade creates come from a ``FOLDS``
function, and a value that must not change gets an ``INVARIANTS`` entry.
"""

import base64
import json
import logging
import math
import os
import re
import shutil
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

LOG = logging.getLogger(__name__)
FROM_VERSION = 14
TO_VERSION = 15
RELEASE = "0.24"
ROOM_FACTOR = 2.2
MIB = 1024**2
ARCHIVE_FORMAT = "openings-archive"
SCHEMA_SQL = Path(__file__).resolve().parents[1] / "schema.sql"


class UpgradeError(Exception):
    """The upgrade was refused or failed; the workspace file is unchanged.

    ``code`` is ``upgrade_room`` (not enough free space), ``upgrade_failed`` (a
    step or a check failed), ``upgrade_state`` (files of an interrupted upgrade
    that cannot be resolved automatically) or ``upgrade_source`` (the file is not
    a complete schema-14 workspace).
    """

    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}


@dataclass(frozen=True)
class Table:
    """A schema-15 table and where its rows come from.

    ``source`` is the schema-14 table the rows are copied from (the same name when
    None); ``fresh`` marks a new table that only ``schema.sql`` and ``FOLDS`` fill.
    ``columns`` maps a schema-15 column to an SQL expression over the schema-14
    row ``o``; every other column present in both tables is copied unchanged, and a
    new column takes its default. ``where`` keeps only the rows it matches: the
    rows it leaves out must be in an archive ``Section``. A copied table is emptied
    first, so rows ``schema.sql`` seeds are replaced by the workspace's own.
    """

    name: str
    source: str | None = None
    columns: dict = field(default_factory=dict)
    where: str = ""
    fresh: bool = False

    @property
    def origin(self):
        return None if self.fresh else self.source or self.name


@dataclass(frozen=True)
class Section:
    """A part of the archive: the rows of ``sql`` over the schema-14 file (``old``).

    ``name`` is the archive key; ``"policy.items"`` is the key ``items`` of the
    object ``policy``. ``shape`` is ``rows`` (a list of objects, one per row),
    ``map`` (an object keyed by the first column; the value is the second column,
    or an object of the others) or ``value`` (the first column of the first row).
    ``tables`` names the schema-14 tables the section archives whole, so they are
    not archived again as dropped tables. Text is kept as stored (JSON stays a
    string); BLOB values are written as ``{"base64": ...}``.
    """

    name: str
    sql: str
    shape: str = "rows"
    tables: tuple = ()


def _repairs(**columns):
    return columns


# #214 Applications and documents: the words of a job's triage, an application's
# stage and a document's kind; the stored Ready mark and per-document review leave
# the schema (archived), responses become replies, and every shortlisted job without
# an open application gets one (FOLDS_214).
TRIAGE_214 = (
    "CASE o.triage WHEN 'inbox' THEN 'new' WHEN 'saved' THEN 'shortlisted' ELSE o.triage END"
)
STATUS_214 = "CASE o.status WHEN 'draft' THEN 'shortlisted' ELSE o.status END"
KIND_214 = "CASE o.kind WHEN 'resume' THEN 'cv' WHEN 'cover_letter' THEN 'letter' ELSE o.kind END"
DOCUMENTS_214 = {
    "kind": KIND_214,
    # Text stored before 0.24 was always derived from the revision's TeX source.
    "text_from": "CASE WHEN o.text IS NOT NULL THEN 'tex' END",
}
REPLIES_214 = {
    # The 0.20 upgrade dated some responses from updated_at; the mark becomes text.
    "note": "CASE WHEN o.estimated=1 THEN o.note || CASE WHEN o.note='' THEN '' "
    "ELSE ' ' END || '(day estimated during the 0.20 upgrade)' ELSE o.note END",
}
READY_COLUMNS_214 = (
    "ready_at",
    "ready_by_kind",
    "ready_by_id",
    "ready_by_name",
    "ready_by_token_kind",
)
SECTIONS_214 = (
    # The stored Ready mark of each application that had one (Ready is computed in 0.24).
    Section(
        "applications_ready",
        "SELECT id," + ",".join(READY_COLUMNS_214) + " FROM old.applications "
        "WHERE ready_at IS NOT NULL ORDER BY id",
        shape="map",
    ),
    # The review state of every document revision (per-document approval is removed).
    Section(
        "document_review_states",
        "SELECT id,review_state FROM old.documents ORDER BY id",
        shape="map",
    ),
)
NOT_ARCHIVED_214 = {
    **{
        f"applications.{name}": "in the archive section applications_ready"
        for name in READY_COLUMNS_214
    },
    "documents.review_state": "in the archive section document_review_states",
}


# #215 Frozen contexts, snapshots and staleness: ``contexts``, ``context_inputs``,
# ``context_parts``, ``snapshot_parts`` and ``snapshot_list_items`` leave the schema
# with ``files.context_id``, ``documents.context_id`` and ``documents.legacy_content``.
# The archive keeps each context with its frame and the hashes of its parts
# (``contexts``), each snapshot part once by hash (``snapshot_parts``), each context
# file without its bytes (``context_files``) and the legacy content of each document
# (``legacy_content``). A context file is a frozen copy of a Career or template file:
# its row is not copied, and a blob only context files referenced is dropped (its
# bytes stay in the pre-upgrade copy). Documents keep their files and cited ids.
CONTEXT_ONLY_BLOB_215 = (
    "(EXISTS(SELECT 1 FROM old.snapshot_parts p WHERE p.blob={blob}) OR EXISTS(SELECT 1 "
    "FROM old.files f WHERE f.sha256={blob} AND f.context_id IS NOT NULL)) AND NOT EXISTS("
    "SELECT 1 FROM old.files f WHERE f.sha256={blob} AND f.context_id IS NULL)"
)
CONTEXT_ONLY_BYTES_215 = (
    "SELECT total(length(b.content)) FROM old.blobs b WHERE "
    + CONTEXT_ONLY_BLOB_215.format(blob="b.sha256")
)
SECTIONS_215 = (
    # Each context: its record, frame and inputs, and its parts in order by hash.
    Section(
        "contexts",
        "SELECT c.*,i.created_at AS inputs_created_at,i.profile_version AS "
        "inputs_profile_version,i.instructions_version AS inputs_instructions_version,"
        "i.templates AS inputs_templates,i.knowledge AS inputs_knowledge,i.claims AS "
        "inputs_claims,i.policy AS inputs_policy,i.parts AS inputs_parts,(SELECT "
        "json_group_array(json_object('position',r.position,'kind',r.kind,'hash',r.hash,"
        "'file_id',r.file_id,'file_created_at',r.file_created_at)) FROM (SELECT cp.position,"
        "p.kind,p.hash,cp.file_id,cp.file_created_at FROM old.context_parts cp JOIN "
        "old.snapshot_parts p ON p.id=cp.part_id WHERE cp.context_id=c.id ORDER BY "
        "cp.position) r) AS parts FROM old.contexts c LEFT JOIN old.context_inputs i ON "
        "i.context_id=c.id ORDER BY c.created_at,c.id",
        tables=("contexts", "context_inputs", "context_parts"),
    ),
    # Each part once: a list part names the hashes of its items in order.
    Section(
        "snapshot_parts",
        "SELECT p.hash,p.kind,p.content,p.blob,CASE WHEN p.kind='list' THEN (SELECT "
        "json_group_array(h) FROM (SELECT t.hash AS h FROM old.snapshot_list_items i JOIN "
        "old.snapshot_parts t ON t.id=i.part_id WHERE i.list_id=p.id ORDER BY i.position)) "
        "END AS items FROM old.snapshot_parts p ORDER BY p.id",
        tables=("snapshot_parts", "snapshot_list_items"),
    ),
    # Context files without their bytes: rendered from parts, or rows of files.
    Section(
        "context_files",
        "SELECT cp.context_id,cp.file_id AS id,p.blob AS sha256,json_extract(p.content,"
        "'$.path') AS name,json_extract(p.content,'$.media_type') AS media_type,"
        "json_extract(p.content,'$.size') AS size,coalesce(cp.file_created_at,c.created_at) "
        "AS created_at FROM old.context_parts cp JOIN old.snapshot_parts p ON p.id=cp.part_id "
        "JOIN old.contexts c ON c.id=cp.context_id WHERE cp.file_id IS NOT NULL "
        "UNION ALL SELECT context_id,id,sha256,name,media_type,size,created_at FROM old.files "
        "WHERE context_id IS NOT NULL ORDER BY 1,2",
    ),
    Section(
        "legacy_content",
        "SELECT id,legacy_content FROM old.documents WHERE legacy_content IS NOT NULL ORDER BY id",
        shape="map",
    ),
)
NOT_ARCHIVED_215 = {
    "documents.legacy_content": "in the archive section legacy_content",
    "files.context_id": "in the archive section context_files",
}


def _log_context_bytes(conn):
    """Log the bytes of the blobs only context files referenced (not copied)."""
    dropped = conn.execute(CONTEXT_ONLY_BYTES_215).fetchone()[0]
    if dropped:
        LOG.warning(
            "The upgrade leaves out %d bytes of files only frozen contexts used; they remain "
            "in the pre-upgrade copy.",
            int(dropped),
        )
    return {}


# Every schema-15 table, parents before the tables that reference them.
TABLES = (
    # #213: the general instructions become Writing rules (``PREFERENCE_SECTIONS``).
    Table("settings", where="o.key<>'instructions'"),
    Table("api_tokens"),
    # #213: the label of the policy rule that dismissed a job becomes its reason.
    # #214: the triage words of 0.24.
    Table(
        "jobs",
        columns={
            "dismissed_reason": "CASE WHEN o.dismissed_reason='' AND o.dismissed_rule_label "
            "IS NOT NULL THEN o.dismissed_rule_label ELSE o.dismissed_reason END",
            "triage": TRIAGE_214,
        },
    ),
    Table("sources"),
    Table("postings"),
    Table("job_identities"),
    Table("posting_details"),
    Table("applications", columns={"status": STATUS_214}),
    Table("runs"),
    Table("events"),
    Table("notes"),
    Table("knowledge"),
    # #211: default_in_cv becomes always_include; role and group fold into metadata.
    Table("claims", columns={"always_include": "o.default_in_cv"}),
    # #213: rule statements leave the template for Writing rules; the rest stays.
    # #214: the template kinds of 0.24.
    Table(
        "templates",
        columns={
            "rules": "CASE WHEN o.rules IS NOT NULL AND json_valid(o.rules) THEN "
            "CASE WHEN json_type(o.rules,'$.statements') IS NULL THEN o.rules "
            "ELSE json_remove(o.rules,'$.statements') END ELSE '{}' END",
            "kind": KIND_214,
        },
    ),
    # #215: frozen contexts leave the schema (archived); so do their files and the
    # bytes only they referenced (kept in the pre-upgrade copy).
    Table("documents", columns=DOCUMENTS_214),
    Table("blobs", where=f"NOT ({CONTEXT_ONLY_BLOB_215.format(blob='o.sha256')})"),
    Table("files", where="o.context_id IS NULL"),
    Table("transfer_grants"),
    Table("collection_runs"),
    Table("tasks"),
    Table("providers"),
    Table("questions"),
    Table("requests"),
    Table("preference_sections", fresh=True),
    Table("replies", source="responses", columns=REPLIES_214),
    Table("skill_notes"),
    Table("job_signals"),
    Table("idempotency_keys"),
)

# JSON columns that gain a json_valid CHECK in schema 15, with the value a stored
# text that is not JSON is replaced by. The original goes to the archive
# (``repaired_json``); the row is always kept.
JSON_REPAIRS = {
    "jobs": _repairs(overrides="'{}'"),
    "sources": _repairs(config="'{}'", schedule="'{}'"),
    "postings": _repairs(payload="'{}'"),
    "applications": _repairs(questions="'[]'", answers="'{}'"),
    "events": _repairs(payload="'{}'"),
    "knowledge": _repairs(metadata="'{}'"),
    "claims": _repairs(metadata="'{}'"),
    "templates": _repairs(rules="'{}'"),
    "documents": _repairs(content="'{}'"),
    "transfer_grants": _repairs(payload="'{}'"),
    "tasks": _repairs(payload="'{}'", result="'{}'"),
}

# Sections of the archive beside the generated ones: ``dropped_columns`` (every
# non-default value of a schema-14 column that schema 15 does not have, by key),
# ``repaired_json`` (stored texts that were not JSON) and ``dropped_tables``
# (every row of a schema-14 table nothing copies or archives). Each removal adds
# its section here with the tables it archives whole.
SECTIONS = (*SECTIONS_214, *SECTIONS_215)

# Dropped columns not written to ``dropped_columns``, each with the reason.
NOT_ARCHIVED = {**NOT_ARCHIVED_214, **NOT_ARCHIVED_215}

# --- #213 Preferences replace Policy -------------------------------------------------
#
# ``policy_sections`` and ``policy_items`` become five free-text sections in
# ``preference_sections``; the general instructions and the rule statements of
# templates become Writing rules; the "No reply" item and the language rule become
# the settings ``no_reply_days`` and ``spoken_languages`` (setting ``workspace``).
# Each item's label, statement and note are kept byte for byte inside its new text.
# The originals are archived whole under ``policy``.

PREFERENCE_SECTIONS = (
    Section("policy.sections", "SELECT * FROM old.policy_sections", tables=("policy_sections",)),
    Section(
        "policy.items",
        "SELECT * FROM old.policy_items ORDER BY section,position,created_at,id",
        tables=("policy_items",),
    ),
    Section(
        "policy.general_instructions",
        "SELECT key,data,version,updated_at FROM old.settings WHERE key='instructions'",
    ),
    Section(
        "policy.template_rules",
        "SELECT id,name,kind,rules FROM old.templates WHERE CASE WHEN rules IS NOT NULL AND "
        "json_valid(rules) THEN json_type(rules,'$.statements') IS NOT NULL ELSE 1 END",
    ),
)
SECTIONS = (*SECTIONS, *PREFERENCE_SECTIONS)
NOT_ARCHIVED = {
    **NOT_ARCHIVED,
    "context_inputs.instructions_version": "derived from the frozen payload, which is kept",
    "context_inputs.policy": "derived from the frozen payload, which is kept",
}
PREFERENCES_SETTING = "workspace"
_POLICY_ORDER = ("decision", "eligibility", "writing", "facts")
_NO_REPLY_LABEL = re.compile(r"\bno[\s-]?(reply|response)\b", re.IGNORECASE)
_DAYS = re.compile(r"^\s*(\d{1,4})(\s*days?)?\s*$", re.IGNORECASE)
# English language names a language rule may hold, with their ISO 639-1 code.
_LANGUAGES = {
    "english": "en",
    "german": "de",
    "french": "fr",
    "italian": "it",
    "spanish": "es",
    "dutch": "nl",
    "flemish": "nl",
    "portuguese": "pt",
    "polish": "pl",
    "swedish": "sv",
    "danish": "da",
    "norwegian": "no",
    "finnish": "fi",
    "czech": "cs",
    "russian": "ru",
    "japanese": "ja",
    "chinese": "zh",
    "mandarin": "zh",
    "arabic": "ar",
    "turkish": "tr",
    "korean": "ko",
}


def _rendered(value):
    """A typed policy value as plain text."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (int, float, str)):
        return str(value)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return ", ".join(value)
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def _statement_text(label, statement):
    """``label: statement``, or the statement alone when it repeats the label."""
    if not statement:
        return label
    if not label or label.strip().casefold() in statement.casefold():
        return statement
    return f"{label}: {statement}"


def _actor_label(kind, name, token_kind):
    if kind == "token" and token_kind == "agent":
        return f"agent:{name or 'token'}"
    return "owner" if kind in ("owner", "token") else "system"


def _loaded(text):
    try:
        return json.loads(text) if text is not None else None
    except ValueError:
        return text


def _policy_text(item):
    """The text of one policy item, with its value, note, rule and confirmation."""
    text = _statement_text(item["label"], item["statement"])
    value = _loaded(item["value"])
    if value is not None:
        rendered = _rendered(value)
        text = f"{text}: {rendered}" if not item["statement"] else f"{text} ({rendered})"
    if item["note"]:
        text += f" — note: {item['note']}"
    rule = _loaded(item["rule"])
    if isinstance(rule, dict):
        condition = rule.get("condition") or {}
        text += (
            f" (Automatic rule removed in 0.24: {rule.get('signal')} "
            f"{condition.get('operator')} {_rendered(condition.get('value'))} → "
            f"{rule.get('action')})"
        )
    if item["confirmed_at"] is None:
        by = _actor_label(
            item["updated_by_kind"] or item["created_by_kind"],
            item["updated_by_name"] or item["created_by_name"],
            item["updated_by_token_kind"] or item["created_by_token_kind"],
        )
        text = f"(proposed by {by}, not confirmed) {text}"
    return text


def _reply_days(value):
    """The days a "No reply" value states (45, "45" or "45 days"), within 1-365."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and float(value).is_integer():
        days = int(value)
    elif isinstance(value, str) and (match := _DAYS.match(value)):
        days = int(match.group(1))
    else:
        return None
    return days if 1 <= days <= 365 else None


def _language_codes(values):
    codes = []
    for value in values if isinstance(values, list) else ():
        key = str(value).strip().casefold()
        code = key if re.fullmatch(r"[a-z]{2}", key) else _LANGUAGES.get(key)
        if code and code not in codes:
            codes.append(code)
    return codes


def _paragraphs(text):
    return [part.strip() for part in re.split(r"\n\s*\n", text or "") if part.strip()]


def _decision_target(item, rule, no_reply, languages):
    """Where a decision item goes; a language rule adds its languages to ``languages``."""
    condition = rule.get("condition") or {}
    if no_reply and item["id"] == no_reply[0]:
        return "facts"
    if rule.get("signal") == "language_required" and condition.get("operator") == "not_in":
        for code in _language_codes(condition.get("value")):
            if code not in languages:
                languages.append(code)
        return "facts"
    return "ruled_out" if rule.get("action") == "dismiss" else "looking_for"


def _template_rules(conn):
    """Writing rules from the rule statements of each template."""
    result = []
    for template in conn.execute(
        "SELECT name,kind,rules FROM old.templates ORDER BY kind DESC,name,id"
    ):
        rules = _loaded(template["rules"])
        statements = rules.get("statements") if isinstance(rules, dict) else None
        if not isinstance(statements, list):
            continue
        scope = "cv" if template["kind"] == "resume" else "letter"
        for statement in sorted(
            (item for item in statements if isinstance(item, dict)),
            key=lambda item: item.get("position") if isinstance(item.get("position"), int) else 0,
        ):
            text = _statement_text(
                str(statement.get("label") or ""), str(statement.get("statement") or "")
            )
            if text:
                result.append(
                    {"text": f"{text} (from template {template['name']})", "scope": scope}
                )
    return result


def fold_preferences(conn):
    """Fill ``preference_sections`` and the ``workspace`` setting from schema 14."""
    sections = {name: [] for name in ("looking_for", "ruled_out", "facts", "writing")}
    no_reply, languages = None, []
    conn.row_factory = sqlite3.Row
    try:
        items = sorted(
            (dict(row) for row in conn.execute("SELECT * FROM old.policy_items")),
            key=lambda item: (
                _POLICY_ORDER.index(item["section"]),
                item["position"],
                item["created_at"],
                item["id"],
            ),
        )
        # The no-reply period: a confirmed item before a proposal, then policy order.
        for item in sorted(items, key=lambda item: item["confirmed_at"] is None):
            if item["section"] == "decision" and _NO_REPLY_LABEL.search(item["label"] or ""):
                days = _reply_days(_loaded(item["value"]))
                if days is not None:
                    no_reply = (item["id"], days)
                    break
        for item in items:
            text, rule = _policy_text(item), _loaded(item["rule"])
            if item["section"] == "decision":
                target = _decision_target(
                    item, rule if isinstance(rule, dict) else {}, no_reply, languages
                )
                sections[target].append({"text": text})
            elif item["section"] == "writing":
                sections["writing"].append({"text": text, "scope": item["scope"] or "all"})
            else:
                sections["facts"].append({"text": text})
        for row in conn.execute("SELECT data FROM old.settings WHERE key='instructions'"):
            general = _loaded(row["data"])
            general = general.get("general") if isinstance(general, dict) else None
            for paragraph in _paragraphs(general if isinstance(general, str) else ""):
                sections["writing"].append({"text": paragraph, "scope": "all"})
        sections["writing"] += _template_rules(conn)
    finally:
        conn.row_factory = None
    stamp = datetime.now(UTC).isoformat(timespec="microseconds")
    for name, values in sections.items():
        if values:
            conn.execute(
                "UPDATE main.preference_sections SET items=?,version=1,updated_at=?,"
                "updated_by='system' WHERE section=?",
                (_dump(values), stamp, name),
            )
    setting = {}
    if no_reply:
        setting["no_reply_days"] = no_reply[1]
    if languages:
        setting["spoken_languages"] = languages
    if not setting:
        return {}
    conn.execute(
        "INSERT INTO main.settings(key,data,version,updated_at) VALUES(?,?,1,?)",
        (PREFERENCES_SETTING, _dump(setting), stamp),
    )
    return {"settings": 1}


# --- end #213 ------------------------------------------------------------------------

# --- #211 Trim secondary features ----------------------------------------------------
#
# ``claims.default_in_cv`` is copied to ``always_include`` unchanged. ``claims.role``
# and ``claims."group"`` leave the schema: a value other than the default
# (``supporting``, empty) is written into the claim's metadata under ``role`` and
# ``group`` unless the metadata already has that key (or is not an object); every
# such value is archived under ``claim_fields``, with ``conflict`` set when one could
# not be written. ``job_signals.welcome`` leaves the schema; non-empty values are
# archived under ``job_signals_welcome``. The other signals are copied unchanged.

TRIM_SECTIONS = (
    Section(
        "claim_fields",
        'SELECT o.id,o.role,o."group",o.default_in_cv,CASE WHEN json_valid(o.metadata) AND '
        "json_type(o.metadata)='object' THEN (o.role<>'supporting' AND "
        "json_type(o.metadata,'$.role') IS NOT NULL) OR (o.\"group\"<>'' AND "
        "json_type(o.metadata,'$.group') IS NOT NULL) ELSE 1 END AS conflict "
        "FROM old.claims AS o WHERE o.role<>'supporting' OR o.\"group\"<>'' ORDER BY o.id",
    ),
    Section(
        "job_signals_welcome",
        "SELECT job_id,welcome FROM old.job_signals WHERE welcome<>'[]' ORDER BY job_id",
    ),
)
SECTIONS = (*SECTIONS, *TRIM_SECTIONS)
NOT_ARCHIVED = {
    **NOT_ARCHIVED,
    "claims.default_in_cv": "copied to claims.always_include",
    "claims.role": "folded into claims.metadata and archived in claim_fields",
    "claims.group": "folded into claims.metadata and archived in claim_fields",
    "job_signals.welcome": "archived in job_signals_welcome",
}


def fold_claim_fields(conn):
    """Write each claim's non-default role and group into its metadata (no new rows)."""
    for column, default in (("role", "supporting"), ("group", "")):
        conn.execute(
            f"UPDATE main.claims SET metadata=json_set(metadata,'$.{column}',"
            f'(SELECT o."{column}" FROM old.claims AS o WHERE o.id=main.claims.id)) '
            f"WHERE json_type(metadata)='object' AND json_type(metadata,'$.{column}') IS NULL "
            f'AND id IN (SELECT o.id FROM old.claims AS o WHERE o."{column}"<>?)',
            (default,),
        )
    return {}


# --- end #211 ------------------------------------------------------------------------

# Functions run after the copy in the same transaction, in order. Each takes the
# connection (schema 15 as ``main``, schema 14 as ``old``) and returns the number
# of rows it created per schema-15 table, which the row-count check adds.


# #214: every shortlisted job without an open application gets one, as shortlisting
# starts it in 0.24; each stored Ready mark leaves an event dated when it was set.
def _start_shortlisted(conn):
    """A Shortlisted application for every shortlisted job without an open one."""
    stamp = datetime.now(UTC).isoformat(timespec="microseconds")
    jobs = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM main.jobs j WHERE triage='shortlisted' AND NOT EXISTS("
            "SELECT 1 FROM main.applications a WHERE a.job_id=j.id AND a.status<>'closed') "
            "ORDER BY created_at,id"
        )
    ]
    for job_id in jobs:
        application_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO main.applications(id,job_id,status,from_shortlist,created_at,updated_at) "
            "VALUES(?,?,'shortlisted',1,?,?)",
            (application_id, job_id, stamp, stamp),
        )
        conn.execute(
            "INSERT INTO main.events(id,job_id,application_id,kind,payload,created_at,"
            "subject_type,subject_id,actor_kind) VALUES(?,?,?,'application_created',?,?,"
            "'application',?,'system')",
            (
                uuid.uuid4().hex,
                job_id,
                application_id,
                json.dumps({"status": "shortlisted", "by": "upgrade"}),
                stamp,
                application_id,
            ),
        )
    return {"applications": len(jobs), "events": len(jobs)}


def _archive_ready_marks(conn):
    """An event per stored Ready mark, dated and attributed as the mark was."""
    rows = conn.execute(
        "SELECT id,job_id," + ",".join(READY_COLUMNS_214) + " FROM old.applications "
        "WHERE ready_at IS NOT NULL ORDER BY id"
    ).fetchall()
    for application_id, job_id, ready_at, kind, actor_id, name, token_kind in rows:
        conn.execute(
            "INSERT INTO main.events(id,job_id,application_id,kind,payload,created_at,"
            "subject_type,subject_id,actor_kind,actor_id,actor_name,actor_token_kind) "
            "VALUES(?,?,?,'application_ready_mark_archived',?,?,'application',?,?,?,?,?)",
            (
                uuid.uuid4().hex,
                job_id,
                application_id,
                json.dumps({"ready_at": ready_at, "by": "upgrade"}),
                ready_at,
                application_id,
                kind,
                actor_id,
                name,
                token_kind,
            ),
        )
    return {"events": len(rows)}


FOLDS_214 = (_start_shortlisted, _archive_ready_marks)
FOLDS = (fold_preferences, fold_claim_fields, *FOLDS_214, _log_context_bytes)

# Values the upgrade must keep: (what, query over schema 15, query over schema 14).
INVARIANTS = (
    (
        # Without the applications the upgrade starts for shortlisted jobs (#214).
        "applications that are not Closed",
        (
            "SELECT count(*) FROM main.applications a WHERE status<>'closed' AND NOT EXISTS("
            "SELECT 1 FROM main.events e WHERE e.application_id=a.id "
            "AND e.kind='application_created' AND json_extract(e.payload,'$.by')='upgrade')"
        ),
        "SELECT count(*) FROM old.applications WHERE status<>'closed'",
    ),
    # #214
    (
        "shortlisted jobs",
        "SELECT count(*) FROM main.jobs WHERE triage='shortlisted'",
        "SELECT count(*) FROM old.jobs WHERE triage='saved'",
    ),
    (
        "shortlisted jobs without an open application",
        (
            "SELECT count(*) FROM main.jobs j WHERE triage='shortlisted' AND NOT EXISTS(SELECT 1 "
            "FROM main.applications a WHERE a.job_id=j.id AND a.status<>'closed')"
        ),
        "SELECT 0",
    ),
    (
        "CV and letter revisions with a PDF",
        (
            "SELECT count(*) FROM main.documents d WHERE kind IN ('cv','letter') AND EXISTS("
            "SELECT 1 FROM main.files f WHERE f.document_id=d.id AND f.media_type='application/pdf')"
        ),
        (
            "SELECT count(*) FROM old.documents d WHERE kind IN ('resume','cover_letter') AND EXISTS("
            "SELECT 1 FROM old.files f WHERE f.document_id=d.id AND f.media_type='application/pdf')"
        ),
    ),
    (
        "dismissed jobs (#213 keeps rule dismissals)",
        "SELECT count(*) FROM main.jobs WHERE triage='dismissed'",
        "SELECT count(*) FROM old.jobs WHERE triage='dismissed'",
    ),
    (
        "claims always included (#211)",
        "SELECT count(*) FROM main.claims WHERE always_include=1",
        "SELECT count(*) FROM old.claims WHERE default_in_cv=1",
    ),
    (
        # #215: without the bytes only frozen contexts referenced.
        "bytes of stored files",
        "SELECT total(length(content)) FROM main.blobs",
        f"SELECT total(length(content))-({CONTEXT_ONLY_BYTES_215}) FROM old.blobs",
    ),
    # #215
    (
        "document revisions, their files and cited ids",
        (
            "SELECT count(*)||' '||total(length(claim_ids)+length(knowledge_ids))||' '||(SELECT "
            "count(*) FROM main.files WHERE document_id IS NOT NULL) FROM main.documents"
        ),
        (
            "SELECT count(*)||' '||total(length(claim_ids)+length(knowledge_ids))||' '||(SELECT "
            "count(*) FROM old.files WHERE document_id IS NOT NULL) FROM old.documents"
        ),
    ),
)


@dataclass(frozen=True)
class Files:
    database: Path
    next: Path
    pre_upgrade: Path
    archive: Path


def files(path):
    """The files of an upgrade of the database at ``path``."""
    path = Path(path)
    return Files(
        database=path,
        next=path.with_name(path.name + ".next"),
        pre_upgrade=path.with_name(f"{path.stem}.pre-{RELEASE}.sqlite"),
        archive=path.with_name(f"{path.stem}.pre-{RELEASE}-archive.json"),
    )


def upgrade(path, schema=None):
    """Upgrade the schema-14 workspace at ``path`` to schema 15 (steps 1 to 6)."""
    paths = files(Path(path).resolve())
    schema = SCHEMA_SQL.read_text() if schema is None else schema
    _check_room(paths.database, schema)
    report = convert(paths.database, paths.next, paths.archive, schema)
    _swap(paths)
    LOG.warning(
        "Upgraded the workspace to schema %d. The schema-%d file is kept as %s and the "
        "removed records are archived in %s.",
        TO_VERSION,
        FROM_VERSION,
        paths.pre_upgrade,
        paths.archive,
    )
    LOG.info("Upgrade report: %s", json.dumps(report, sort_keys=True))
    return report


def recover(path):
    """Resolve the files an interrupted upgrade left beside the database (step 7).

    The database missing while the new file and the pre-upgrade copy exist means
    the swap stopped between its two renames, after every check passed: it is
    finished. A new file beside the database is an unfinished upgrade: it is
    removed and the upgrade runs again.
    """
    paths = files(Path(path).resolve())
    if paths.database.exists():
        if paths.next.exists():
            _remove(paths.next)
            _remove(_temporary(paths.archive))
            LOG.warning("Removed %s, left by an interrupted upgrade.", paths.next)
        return
    if paths.next.exists() and paths.pre_upgrade.exists():
        _replace(paths.next, paths.database)
        _fsync_directory(paths.database.parent)
        LOG.warning(
            "Finished an interrupted upgrade: %s is the schema-%d workspace and %s the "
            "schema-%d copy.",
            paths.database,
            TO_VERSION,
            paths.pre_upgrade,
            FROM_VERSION,
        )
    elif paths.next.exists() or paths.pre_upgrade.exists():
        present = paths.next if paths.next.exists() else paths.pre_upgrade
        raise UpgradeError(
            "upgrade_state",
            f"{paths.database.name} is missing but {present.name} is in {present.parent}. "
            f"To go back to Openings 0.23, move {paths.pre_upgrade.name} to "
            f"{paths.database.name} and start the 0.23 image; to start a new workspace, move "
            f"{present.name} out of the folder.",
        )


def convert(source, target, archive, schema=None):
    """Copy the schema-14 file ``source`` into a new schema-15 file ``target`` (steps 2-5).

    ``source`` is only read (after a checkpoint of its write-ahead log). The archive
    is written to ``archive``. On failure ``target`` and the archive are removed
    and ``UpgradeError`` is raised. Returns the counts of the conversion.
    """
    source, target, archive = Path(source), Path(target), Path(archive)
    schema = SCHEMA_SQL.read_text() if schema is None else schema
    for leftover in (target, archive, _temporary(archive)):
        _remove(leftover)
    try:
        _checkpoint(source)
        report = _build(source, target, archive, schema)
        _verify(source, target, archive, report)
        return report
    except Exception as error:
        for leftover in (target, archive, _temporary(archive)):
            _remove(leftover)
        if isinstance(error, UpgradeError):
            raise
        raise UpgradeError(
            "upgrade_failed",
            f"The upgrade to Openings {RELEASE} stopped ({error}). The workspace file was not "
            "changed.",
        ) from error


# Planning: what each table copies and what the archive holds.


def _tables(conn, schema):
    """Ordinary tables of ``schema``: name -> without rowid."""
    return {
        row[1]: bool(row[4])
        for row in conn.execute(f"PRAGMA {schema}.table_list")
        if row[2] == "table" and not row[1].startswith("sqlite_")
    }


def _columns(conn, schema, table):
    """Columns of a table: name -> (declared type, default SQL, primary key position)."""
    return {
        row[1]: (row[2], row[4], row[5])
        for row in conn.execute(f'PRAGMA {schema}.table_xinfo("{table}")')
        if row[6] == 0
    }


def _key(columns):
    keys = sorted((pk, name) for name, (_, _, pk) in columns.items() if pk)
    return [name for _, name in keys] or ["rowid"]


def _rowid(columns, without_rowid):
    """Whether rows have a rowid of their own (not an INTEGER PRIMARY KEY)."""
    key = [name for name, (_, _, pk) in columns.items() if pk]
    return not without_rowid and not (len(key) == 1 and columns[key[0]][0].upper() == "INTEGER")


def _quoted(names):
    return ",".join(f'"{name}"' for name in names)


def _plan(conn):
    """The copy statements and archive sections for the attached schema-14 file."""
    new, old = _tables(conn, "main"), _tables(conn, "old")
    listed = [table.name for table in TABLES]
    if sorted(listed) != sorted(new) or len(set(listed)) != len(listed):
        raise UpgradeError(
            "upgrade_failed",
            "The schema-15 tables and the upgrade's table list differ: "
            f"{sorted(set(new) ^ set(listed))}.",
        )
    copies, sections, used = [], list(SECTIONS), set()
    archived = {name for section in SECTIONS for name in section.tables}
    for table in TABLES:
        if table.origin is None:
            copies.append((table, None, None))
            continue
        if table.origin not in old:
            raise UpgradeError(
                "upgrade_source",
                f"The workspace has no {table.origin} table, so it is not a complete schema-"
                f"{FROM_VERSION} workspace.",
            )
        used.add(table.origin)
        target, origin = _columns(conn, "main", table.name), _columns(conn, "old", table.origin)
        repairs = JSON_REPAIRS.get(table.name, {})
        names, values = [], []
        if _rowid(target, new[table.name]) and _rowid(origin, old[table.origin]):
            # Rows keep their rowid: the search index and rowid order depend on it.
            names.append("rowid")
            values.append("o.rowid")
        for name in target:
            if name in table.columns:
                expression = table.columns[name]
            elif name in origin:
                expression = f'o."{name}"'
                if name in repairs:
                    expression = (
                        f'CASE WHEN o."{name}" IS NULL OR json_valid(o."{name}") '
                        f'THEN o."{name}" ELSE {repairs[name]} END'
                    )
            else:
                continue
            names.append(name)
            values.append(expression)
        where = f" WHERE {table.where}" if table.where else ""
        source = f'FROM old."{table.origin}" AS o{where}'
        insert = (
            f'INSERT INTO main."{table.name}"({_quoted(names)}) SELECT {",".join(values)} {source}'
        )
        copies.append((table, insert, f"SELECT count(*) {source}"))
        key = _key(origin)
        selected = ",".join(f'o."{name}"' if name != "rowid" else "o.rowid" for name in key)
        for name, (_, default, _) in origin.items():
            if name in target or f"{table.origin}.{name}" in NOT_ARCHIVED:
                continue
            sections.append(
                Section(
                    f"dropped_columns.{table.origin}.{name}",
                    f'SELECT {selected},o."{name}" AS value FROM old."{table.origin}" AS o '
                    f'WHERE o."{name}" IS NOT {default if default is not None else "NULL"}',
                )
            )
        for name in repairs:
            if name in origin and name not in table.columns:
                sections.append(
                    Section(
                        f"repaired_json.{table.origin}.{name}",
                        f'SELECT {selected},o."{name}" AS value FROM old."{table.origin}" AS o '
                        f'WHERE NOT (o."{name}" IS NULL OR json_valid(o."{name}"))',
                    )
                )
    for name in old:
        if name not in used and name not in archived:
            sections.append(Section(f"dropped_tables.{name}", f'SELECT * FROM old."{name}"'))
    # A generated section is written only when it holds something.
    sections = [section for section in sections if section in SECTIONS or _count(conn, section) > 0]
    return copies, sections


def _count(conn, section):
    return conn.execute(f"SELECT count(*) FROM ({section.sql})").fetchone()[0]


def _estimate(conn, section):
    """Bytes the section takes in the archive, about."""
    names = [d[0] for d in conn.execute(f"SELECT * FROM ({section.sql}) LIMIT 0").description]
    sizes = "+".join(f'length(quote("{name}"))+{len(name) + 6}' for name in names) or "0"
    return conn.execute(f"SELECT total({sizes}) FROM ({section.sql})").fetchone()[0]


# Steps.


def _connect(path, readonly=False):
    uri = Path(path).resolve().as_uri() + ("?mode=ro" if readonly else "")
    conn = sqlite3.connect(uri, uri=True, isolation_level=None)
    conn.execute("PRAGMA foreign_keys=OFF")
    return conn


def _attach(conn, source):
    conn.execute("ATTACH DATABASE ? AS old", (Path(source).resolve().as_uri() + "?mode=ro",))


def _bytes(path):
    total = 0
    for name in (Path(path), Path(str(path) + "-wal")):
        try:
            total += name.stat().st_size
        except FileNotFoundError:
            pass
    return total


def _check_room(path, schema):
    """Step 1: refuse before writing anything when the volume is too small."""
    conn = sqlite3.connect("file::memory:", uri=True, isolation_level=None)
    try:
        conn.executescript(schema)
        _attach(conn, path)
        _, sections = _plan(conn)
        archive = sum(_estimate(conn, section) for section in sections)
    finally:
        conn.close()
    size = _bytes(path)
    needed = math.ceil(ROOM_FACTOR * size + archive)
    free = shutil.disk_usage(Path(path).parent).free
    if free < needed:
        raise UpgradeError(
            "upgrade_room",
            f"Upgrading this workspace to Openings {RELEASE} needs {math.ceil(needed / MIB)} MiB "
            f"of free space on the data volume ({Path(path).parent}); {free // MIB} MiB are free. "
            "Free some space and start again. The workspace file was not changed.",
            {"needed_bytes": needed, "free_bytes": free, "database_bytes": size},
        )


def _checkpoint(source):
    """Move the write-ahead log into the file, so the copy reads one file."""
    conn = sqlite3.connect(source, isolation_level=None)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version != FROM_VERSION:
            raise UpgradeError(
                "upgrade_source", f"The workspace has schema {version}, not {FROM_VERSION}."
            )
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _build(source, target, archive, schema):
    """Steps 2 to 4: the new file, the copy in one transaction and the archive."""
    conn = _connect(target)
    try:
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.execute("PRAGMA synchronous=OFF")
        conn.executescript(schema)
        _attach(conn, source)
        copies, sections = _plan(conn)
        report = {"copied": {}, "created": {}, "expected": {}}
        conn.execute("BEGIN IMMEDIATE")
        for table, insert, count in copies:
            if insert is None:
                report["expected"][table.name] = conn.execute(
                    f'SELECT count(*) FROM main."{table.name}"'
                ).fetchone()[0]
                continue
            conn.execute(f'DELETE FROM main."{table.name}"')
            report["expected"][table.name] = conn.execute(count).fetchone()[0]
            report["copied"][table.name] = conn.execute(insert).rowcount
        for fold in FOLDS:
            for name, created in (fold(conn) or {}).items():
                report["created"][name] = report["created"].get(name, 0) + created
                report["expected"][name] = report["expected"].get(name, 0) + created
        conn.execute("INSERT INTO main.jobs_fts(jobs_fts) VALUES('rebuild')")
        conn.execute("COMMIT")
        report["archive"] = _write_archive(conn, archive, sections)
    finally:
        conn.close()
    _fsync(target)
    return report


def _value(value):
    return {"base64": base64.b64encode(value).decode()} if isinstance(value, bytes) else value


def _dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _write_section(out, conn, section):
    cursor = conn.execute(section.sql)
    names = [d[0] for d in cursor.description]
    written = 0
    if section.shape == "value":
        row = cursor.fetchone()
        out.write(_dump(_value(row[0]) if row else None))
        return 1 if row else 0
    out.write("[" if section.shape == "rows" else "{")
    for row in cursor:
        if written:
            out.write(",")
        if section.shape == "rows":
            out.write(_dump({name: _value(value) for name, value in zip(names, row, strict=True)}))
        else:
            rest = (
                _value(row[1])
                if len(names) == 2
                else {name: _value(value) for name, value in zip(names[1:], row[1:], strict=True)}
            )
            out.write(_dump(str(row[0])) + ":" + _dump(rest))
        written += 1
    out.write("]" if section.shape == "rows" else "}")
    return written


def _groups(sections):
    """Sections by top-level archive key, in order: key -> [(subkey or None, section)]."""
    groups = {}
    for section in sections:
        top, _, sub = section.name.partition(".")
        groups.setdefault(top, []).append((sub or None, section))
    for top, members in groups.items():
        if len(members) > 1 and any(sub is None for sub, _ in members):
            raise UpgradeError("upgrade_failed", f"The archive key {top} is used twice.")
    return groups


def _temporary(path):
    return Path(str(path) + ".tmp")


def _write_archive(conn, path, sections):
    """Step 4: the archive, written to a temporary name and renamed (mode 0600)."""
    counts = {section.name: _count(conn, section) for section in sections}
    temporary = _temporary(path)
    handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        head = {
            "format": ARCHIVE_FORMAT,
            "from_schema": FROM_VERSION,
            "to_schema": TO_VERSION,
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "counts": counts,
        }
        out.write(_dump(head)[:-1])
        for top, members in _groups(sections).items():
            out.write("," + _dump(top) + ":")
            if members[0][0] is None:
                written = {members[0][1].name: _write_section(out, conn, members[0][1])}
            else:
                out.write("{")
                written = {}
                for index, (sub, section) in enumerate(members):
                    out.write(("," if index else "") + _dump(sub) + ":")
                    written[section.name] = _write_section(out, conn, section)
                out.write("}")
            for name, number in written.items():
                if number != counts[name]:
                    raise UpgradeError(
                        "upgrade_failed",
                        f"The archive section {name} has {number} records; its source has "
                        f"{counts[name]}.",
                    )
        out.write("}")
        out.flush()
        os.fsync(out.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    _fsync_directory(path.parent)
    return counts


def _archived(value, section):
    """The number of records of a section as read back from the archive."""
    if section.shape == "value":
        return 0 if value is None else 1
    return len(value)


def _verify(source, target, archive, report):
    """Step 5: the checks that must pass before the new file replaces the original."""
    conn = _connect(target, readonly=True)
    try:
        _attach(conn, source)
        failures = []
        if conn.execute("PRAGMA main.integrity_check").fetchone()[0] != "ok":
            failures.append("the new file failed its integrity check")
        if conn.execute("PRAGMA main.user_version").fetchone()[0] != TO_VERSION:
            failures.append(f"the new file is not at schema {TO_VERSION}")
        renamed = {table.origin: table.name for table in TABLES if table.origin}
        before = {
            (renamed.get(row[0], row[0]), row[1], renamed.get(row[2], row[2]))
            for row in conn.execute("PRAGMA old.foreign_key_check")
        }
        broken = {
            (row[0], row[1], row[2]) for row in conn.execute("PRAGMA main.foreign_key_check")
        } - before
        if broken:
            failures.append(f"{len(broken)} references between records would break")
        for name, expected in report["expected"].items():
            actual = conn.execute(f'SELECT count(*) FROM main."{name}"').fetchone()[0]
            if actual != expected:
                failures.append(f"{name} has {actual} rows instead of {expected}")
        for what, after, earlier in INVARIANTS:
            values = conn.execute(after).fetchone()[0], conn.execute(earlier).fetchone()[0]
            if values[0] != values[1]:
                failures.append(f"{what}: {values[0]} instead of {values[1]}")
        _, sections = _plan(conn)
        with open(archive, encoding="utf-8") as handle:
            data = json.load(handle)
        if data.get("format") != ARCHIVE_FORMAT or data.get("counts") != report["archive"]:
            failures.append("the archive does not read back")
        else:
            for section in sections:
                top, _, sub = section.name.partition(".")
                value = data[top][sub] if sub else data[top]
                if _archived(value, section) != report["archive"][section.name]:
                    failures.append(f"the archive section {section.name} is incomplete")
            if {section.name for section in sections} != set(report["archive"]):
                failures.append("the archive does not hold the expected sections")
            for section in sections:
                if _count(conn, section) != report["archive"][section.name]:
                    failures.append(f"the archive section {section.name} differs from its source")
    finally:
        conn.close()
    if failures:
        raise UpgradeError(
            "upgrade_failed",
            f"The upgrade to Openings {RELEASE} did not pass its checks: "
            + "; ".join(failures)
            + ". The workspace file was not changed.",
            {"failures": failures},
        )


def _swap(paths):
    """Step 6: the original becomes the pre-upgrade copy and the new file takes its name."""
    wal = Path(str(paths.database) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise UpgradeError(
            "upgrade_failed",
            f"{wal.name} still holds changes, so the workspace is in use by another process. "
            "Stop it and start again. The workspace file was not changed.",
        )
    for suffix in ("-wal", "-shm"):
        _remove(Path(str(paths.database) + suffix))
    for suffix in ("", "-wal", "-shm"):
        _remove(Path(str(paths.pre_upgrade) + suffix))
    _replace(paths.database, paths.pre_upgrade)
    _fsync_directory(paths.database.parent)
    _replace(paths.next, paths.database)
    _fsync_directory(paths.database.parent)


# File helpers; _replace is separate so a test can stop the swap between its renames.


def _replace(source, target):
    os.replace(source, target)


def _remove(path):
    for suffix in ("", "-wal", "-shm", "-journal"):
        Path(str(path) + suffix).unlink(missing_ok=True)


def _fsync(path):
    handle = os.open(path, os.O_RDONLY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def _fsync_directory(directory):
    try:
        handle = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(handle)
    except OSError:
        pass
    finally:
        os.close(handle)
