"""The schema 14 to 15 upgrade, on the real fixture written by v0.23.1's own seed.

Each later change of the unreleased migration adds its own block of data
mapping assertions below ("Data mapping").
"""

import gzip
import hashlib
import json
import re
import shutil
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

import pytest

from openings.db import SCHEMA_VERSION, Database
from openings.errors import DomainError
from openings.migrations import m15
from openings.operations import restore_database
from openings.workspace import Workspace

FIXTURE = Path(__file__).with_name("fixtures") / f"workspace-{SCHEMA_VERSION - 1}.sql.gz"

# Ready as 0.24 computes it right after the upgrade, on the schema-14 original: a
# draft whose current CV and letter revisions both have a PDF and that has no
# unresolved blocking requirement.
_LEAF = (
    "EXISTS(SELECT 1 FROM documents d WHERE d.application_id=a.id AND d.kind='{kind}' AND NOT "
    "EXISTS(SELECT 1 FROM documents c WHERE c.previous_id=d.id) AND EXISTS(SELECT 1 FROM files "
    "f WHERE f.document_id=d.id AND f.media_type='application/pdf'))"
)
COMPUTED_READY = (
    "a.status='draft' AND "
    + _LEAF.format(kind="resume")
    + " AND "
    + _LEAF.format(kind="cover_letter")
    + " AND NOT EXISTS(SELECT 1 FROM json_each(a.requirements) r WHERE "
    "json_extract(r.value,'$.blocking') AND NOT coalesce(json_extract(r.value,'$.resolved'),0))"
)

# Tables 0.24 removes (archived whole) and adds (filled by the upgrade's folds).
REMOVED_TABLES = {"policy_sections", "policy_items"}  # #213
ADDED_TABLES = {"preference_sections"}  # #213
REMOVED_TABLES |= {"runs", "questions", "requests", "skill_notes"}  # #209
# #215
REMOVED_TABLES |= {
    "contexts",
    "context_inputs",
    "context_parts",
    "snapshot_parts",
    "snapshot_list_items",
}


class Killed(BaseException):
    """A process stopped from outside: no cleanup code runs."""


def load_fixture(path, change=None):
    """The fixture as a database file, as a schema-14 installation keeps it."""
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(gzip.decompress(FIXTURE.read_bytes()).decode())
        if change:
            conn.executescript(change)
        conn.commit()
    return path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def query(path, sql, params=()):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(sql, params).fetchall()


def tables(conn):
    return [
        row[1]
        for row in conn.execute("PRAGMA table_list")
        if row[0] == "main"
        and row[2] in ("table", "virtual", "shadow")
        and not row[1].startswith("sqlite_")
    ]


def structure(path):
    """Every object's normalised SQL, columns, references and indexes."""
    with closing(sqlite3.connect(path)) as conn:
        objects = {
            (kind, name): re.sub(r"\s+", " ", sql or "").strip()
            for kind, name, sql in conn.execute("SELECT type,name,sql FROM sqlite_master")
        }
        details = {
            name: (
                conn.execute(f'PRAGMA table_xinfo("{name}")').fetchall(),
                conn.execute(f'PRAGMA foreign_key_list("{name}")').fetchall(),
                sorted(row[1:] for row in conn.execute(f'PRAGMA index_list("{name}")')),
            )
            for name in tables(conn)
        }
        return objects, details, conn.execute("PRAGMA user_version").fetchone()[0]


def counts(path):
    """Rows per table, without the tables 0.24 removes or adds."""
    with closing(sqlite3.connect(path)) as conn:
        return {
            name: conn.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            for name in tables(conn)
            if not name.startswith("jobs_fts") and name not in REMOVED_TABLES | ADDED_TABLES
        }


# Tables the upgrade renames: schema-15 name -> schema-14 name.
RENAMED = {"replies": "responses"}  # #214


def created_by_upgrade(pre_upgrade):
    """Rows the upgrade's folds add, per schema-15 table, counted on the original."""
    created = {}
    # #214: an application (and its event) per shortlisted job without an open one,
    # and an event per stored Ready mark.
    started = query(
        pre_upgrade,
        "SELECT count(*) FROM jobs j WHERE triage='saved' AND NOT EXISTS(SELECT 1 FROM "
        "applications a WHERE a.job_id=j.id AND a.status<>'closed')",
    )[0][0]
    marks = query(pre_upgrade, "SELECT count(*) FROM applications WHERE ready_at IS NOT NULL")[0][0]
    created["applications"] = created.get("applications", 0) + started
    created["events"] = created.get("events", 0) + started + marks
    # #209: a note per answered question and per request about an existing job or
    # application.
    notes = query(
        pre_upgrade,
        "SELECT (SELECT count(*) FROM questions q WHERE state='answered' AND ("
        "q.job_id IN (SELECT id FROM jobs) OR q.application_id IN (SELECT id FROM applications)))"
        "+(SELECT count(*) FROM requests r WHERE r.job_id IN (SELECT id FROM jobs) "
        "OR r.application_id IN (SELECT id FROM applications))",
    )[0][0]
    created["notes"] = created.get("notes", 0) + notes
    return created


# #215: context files and the blobs only they referenced are not copied.
CONTEXT_ONLY_BLOBS = (
    "SELECT count(*) FROM blobs b WHERE (EXISTS(SELECT 1 FROM snapshot_parts p WHERE "
    "p.blob=b.sha256) OR EXISTS(SELECT 1 FROM files f WHERE f.sha256=b.sha256 AND f.context_id "
    "IS NOT NULL)) AND NOT EXISTS(SELECT 1 FROM files f WHERE f.sha256=b.sha256 AND "
    "f.context_id IS NULL)"
)


def left_out_by_upgrade(pre_upgrade):
    """Rows of kept tables the upgrade does not copy, per schema-15 table."""
    return {
        "files": query(pre_upgrade, "SELECT count(*) FROM files WHERE context_id IS NOT NULL")[0][
            0
        ],
        "blobs": query(pre_upgrade, CONTEXT_ONLY_BLOBS)[0][0],
    }


def expected_counts(original, pre_upgrade):
    """The row counts of the upgraded file: the original's, renamed, plus folded rows."""
    renamed = {old: new for new, old in RENAMED.items()}
    expected = {renamed.get(name, name): number for name, number in original.items()}
    for name, number in created_by_upgrade(pre_upgrade).items():
        expected[name] += number
    for name, number in left_out_by_upgrade(pre_upgrade).items():
        expected[name] -= number
    return expected


@pytest.fixture(scope="module")
def upgraded(tmp_path_factory):
    """The fixture upgraded at startup, once per module and only read by the tests:
    (database, pre-upgrade copy, archive, input digest, input counts, files beside it)."""
    path = load_fixture(tmp_path_factory.mktemp("upgraded") / "openings.sqlite")
    before, original = digest(path), counts(path)
    Database(path)
    files = m15.files(path)
    beside = sorted(p.name for p in path.parent.iterdir())
    return path, files.pre_upgrade, files.archive, before, original, beside


def test_an_upgraded_workspace_is_a_new_one_holding_every_row_of_the_original(tmp_path, upgraded):
    path, pre_upgrade, archive, before, original, beside = upgraded
    Database(tmp_path / "fresh.sqlite")
    assert structure(path) == structure(tmp_path / "fresh.sqlite")
    assert query(path, "PRAGMA integrity_check") == [("ok",)]
    assert query(path, "PRAGMA foreign_key_check") == []
    # The original is kept byte for byte and every row is copied.
    assert digest(pre_upgrade) == before
    assert query(pre_upgrade, "PRAGMA user_version") == [(14,)]
    assert counts(path) == expected_counts(original, pre_upgrade)
    assert query(path, "SELECT count(*) FROM jobs_fts WHERE jobs_fts MATCH 'engineer'")[0][0] > 0
    assert beside == sorted([path.name, pre_upgrade.name, archive.name])


# Data mapping: one block per change of the migration.


def test_generic_changes_keep_every_value(upgraded):
    path, pre_upgrade = upgraded[:2]
    # Ids, versions and every kept value are copied unchanged.
    # Rows an upgrade fold adds (#214) are not in the original.
    for table, columns in (
        ("jobs", "id,title,company,posting,version,created_at"),
        ("applications", "id,job_id,outcome,version,questions,answers,requirements"),
        ("events", "id,job_id,application_id,payload,subject_id"),
        ("documents", "id,previous_id,text,claim_ids"),
        ("blobs", "sha256,content,size"),
    ):
        sql = f"SELECT rowid,{columns} FROM {table} ORDER BY rowid"
        if table == "blobs":
            sql = f"SELECT {columns} FROM {table} ORDER BY sha256"
        assert query(path, sql)[: len(old := query(pre_upgrade, sql))] == old
    # #218: career entries and highlights take the words of 0.24 in the change log.
    renamed = {"knowledge": "career", "claim": "highlight"}
    sql = "SELECT rowid,kind,subject_type FROM events ORDER BY rowid"
    for (_, kind, subject), (_, new_kind, new_subject) in zip(
        query(pre_upgrade, sql), query(path, sql), strict=False
    ):
        prefix = kind.split("_", 1)[0]
        assert new_kind == (renamed[prefix] + kind[len(prefix) :] if prefix in renamed else kind)
        assert new_subject == renamed.get(subject, subject)
    # An estimated response day becomes text on the response.
    old = query(pre_upgrade, "SELECT id,note FROM responses WHERE estimated=1")
    assert old
    for response_id, note in old:
        expected = (note + " " if note else "") + "(day estimated during the 0.20 upgrade)"
        assert query(path, "SELECT note FROM replies WHERE id=?", (response_id,)) == [(expected,)]
    assert query(path, "SELECT count(*) FROM pragma_table_info('notes') WHERE name='origin'") == [
        (0,)
    ]
    # job_identities keeps its rows without a rowid.
    assert query(path, "SELECT identity,job_id FROM job_identities ORDER BY 1,2") == query(
        pre_upgrade, "SELECT identity,job_id FROM job_identities ORDER BY 1,2"
    )


def test_text_that_is_not_json_is_repaired_and_archived(tmp_path):
    path = load_fixture(
        tmp_path / "openings.sqlite",
        "UPDATE jobs SET overrides='not json' WHERE rowid=(SELECT min(rowid) FROM jobs);",
    )
    job_id = query(path, "SELECT id FROM jobs WHERE overrides='not json'")[0][0]
    Database(path)
    assert query(path, "SELECT overrides FROM jobs WHERE id=?", (job_id,)) == [("{}",)]
    archive = json.loads(m15.files(path).archive.read_text())
    assert archive["repaired_json"]["jobs.overrides"] == [{"id": job_id, "value": "not json"}]
    assert archive["counts"]["repaired_json.jobs.overrides"] == 1


# #214 Applications and documents.


def test_applications_and_documents_take_the_words_of_0_24(upgraded):
    path, pre_upgrade, archive_path = upgraded[:3]
    archive = json.loads(archive_path.read_text())
    # Triage, stage and kinds.
    triage = {"inbox": "new", "saved": "shortlisted", "dismissed": "dismissed"}
    old_jobs = dict(query(pre_upgrade, "SELECT id,triage FROM jobs"))
    assert dict(query(path, "SELECT id,triage FROM jobs")) == {
        key: triage[value] for key, value in old_jobs.items()
    }
    old_status = dict(query(pre_upgrade, "SELECT id,status FROM applications"))
    new_status = dict(query(path, "SELECT id,status FROM applications"))
    assert {key: new_status[key] for key in old_status} == {
        key: "shortlisted" if value == "draft" else value for key, value in old_status.items()
    }
    assert query(path, "SELECT DISTINCT required_documents FROM applications") == [
        ('["cv","letter"]',)
    ]
    kinds = {"resume": "cv", "cover_letter": "letter"}
    for table in ("documents", "templates"):
        old_kinds = dict(query(pre_upgrade, f"SELECT id,kind FROM {table}"))
        assert dict(query(path, f"SELECT id,kind FROM {table}")) == {
            key: kinds.get(value, value) for key, value in old_kinds.items()
        }
    # Text derived from TeX is kept and says so; review states go to the archive.
    assert query(path, "SELECT count(*) FROM documents WHERE text IS NOT NULL") == query(
        path, "SELECT count(*) FROM documents WHERE text_from='tex'"
    )
    assert archive["document_review_states"] == dict(
        query(pre_upgrade, "SELECT id,review_state FROM documents")
    )
    # Replies are the responses, copied with their ids.
    assert query(path, "SELECT id,application_id,kind,date,version FROM replies ORDER BY id") == (
        query(pre_upgrade, "SELECT id,application_id,kind,date,version FROM responses ORDER BY id")
    )


def test_every_shortlisted_job_has_an_open_application_after_the_upgrade(upgraded):
    path, pre_upgrade = upgraded[:2]
    waiting = {
        row[0]
        for row in query(
            pre_upgrade,
            "SELECT id FROM jobs j WHERE triage='saved' AND NOT EXISTS(SELECT 1 FROM "
            "applications a WHERE a.job_id=j.id AND a.status<>'closed')",
        )
    }
    assert waiting
    old_ids = {row[0] for row in query(pre_upgrade, "SELECT id FROM applications")}
    started = [
        row[1:]
        for row in query(
            path,
            "SELECT a.id,a.job_id,a.status,a.from_shortlist,e.actor,"
            "json_extract(e.payload,'$.by') FROM applications a JOIN events e "
            "ON e.application_id=a.id AND e.kind='application_created'",
        )
        if row[0] not in old_ids
    ]
    assert {row[0] for row in started} == waiting and len(started) == len(waiting)
    assert {row[1:] for row in started} == {("shortlisted", 1, "system", "upgrade")}
    assert query(
        path,
        "SELECT count(*) FROM jobs j WHERE triage='shortlisted' AND NOT EXISTS(SELECT 1 FROM "
        "applications a WHERE a.job_id=j.id AND a.status<>'closed')",
    ) == [(0,)]


def test_stored_ready_marks_are_archived_with_an_event_and_ready_is_computed(tmp_path, upgraded):
    path, pre_upgrade, archive_path = upgraded[:3]
    archive = json.loads(archive_path.read_text())
    marks = query(
        pre_upgrade,
        "SELECT id,ready_at,ready_by_kind,ready_by_name FROM applications WHERE ready_at IS NOT NULL",
    )
    assert marks
    assert {
        key: (value["ready_at"], value["ready_by_kind"], value["ready_by_name"])
        for key, value in archive["applications_ready"].items()
    } == {row[0]: row[1:] for row in marks}
    events = query(
        path,
        "SELECT application_id,created_at,actor FROM events "
        "WHERE kind='application_ready_mark_archived'",
    )
    # #209: attributed with the actor label of who set the mark.
    labelled = query(
        pre_upgrade,
        f"SELECT id,ready_at,{LABEL.format('ready_by')} FROM applications "
        "WHERE ready_at IS NOT NULL",
    )
    assert sorted(events) == sorted(labelled)
    # Ready is computed: the upgraded workspace lists what the rule of 0.24 computes
    # on the original, whatever the stored marks said.
    computed = {
        row[0]
        for row in query(pre_upgrade, "SELECT id FROM applications a WHERE " + COMPUTED_READY)
    }
    # The shared upgraded file is only read: the workspace opens a copy.
    copy = tmp_path / "openings.sqlite"
    shutil.copyfile(path, copy)
    listed = Workspace(copy).list_applications(stage="ready", limit=200)
    assert {item["id"] for item in listed["items"]} == computed
    assert listed["stage_counts"]["ready"] == len(computed)


# #213 Preferences replace Policy.


def preferences(path):
    rows = query(path, "SELECT section,items,version,updated_by FROM preference_sections")
    return {section: (json.loads(items), version, by) for section, items, version, by in rows}


def texts(path, section):
    return [item["text"] for item in preferences(path)[section][0]]


def test_policy_becomes_preferences_and_writing_rules_and_the_archive_keeps_it(upgraded):
    path, pre_upgrade, archive_path = upgraded[:3]
    sections = preferences(path)
    assert set(sections) == {"looking_for", "ruled_out", "facts", "writing", "working_with_me"}
    # A decision item goes to What I rule out only when its rule dismissed jobs.
    target = (
        "Target roles: Shortlist data, backend and platform engineering roles at mid to senior "
        "level."
    )
    places = (
        "Locations: Dismiss roles that need me on site outside these places. (Zurich, Basel, "
        "Remote, Europe)"
    )
    assert texts(path, "looking_for") == [target, places]
    proposed = (
        "(proposed by agent:career-agent, not confirmed) Postings no longer listed: Dismiss jobs "
        "to review when their source stops listing them. (Automatic rule removed in 0.24: "
        "no_longer_listed is yes → dismiss)"
    )
    assert texts(path, "ruled_out") == [proposed]
    facts = texts(path, "facts")
    # The language rule and the No reply item are kept as text and become settings.
    assert facts[0].startswith("Languages outside my list: Dismiss postings that require")
    assert facts[0].endswith(
        "(Automatic rule removed in 0.24: language_required not_in English, Italian → dismiss)"
    )
    # The statement repeats the label, so it stands alone.
    assert facts[1].startswith('Close an application as "no reply"')
    assert facts[1].endswith("(45 days)")
    assert facts[2] == (
        "Work authorization: EU citizen with a Swiss B permit. (2028-06-30) — note: "
        + query(pre_upgrade, "SELECT note FROM policy_items WHERE label='Work authorization'")[0][0]
    )
    assert facts[4].startswith("(proposed by agent:career-agent, not confirmed) No relocation")
    assert facts[7] == (
        '(proposed by system, not confirmed) Interview availability: {"days": ["Tue", "Thu"], '
        '"from": "16:00", "timezone": "Europe/Zurich"}'
    )
    # #209: the answered question without a subject follows.
    assert len(facts) == 9 and facts[8].startswith("Question from agent:career-agent")
    settings = json.loads(query(path, "SELECT data FROM settings WHERE key='workspace'")[0][0])
    assert settings == {"no_reply_days": 45, "spoken_languages": ["en", "it"]}
    # Every label, statement and note is kept byte for byte, each item exactly once.
    every = [text for section in sections.values() for text in (i["text"] for i in section[0])]
    for label, statement, note in query(
        pre_upgrade, "SELECT label,statement,note FROM policy_items"
    ):
        # A label the statement repeats is left out.
        named = label if label.casefold() not in statement.casefold() else ""
        holding = [text for text in every if statement in text and named in text and note in text]
        assert len(holding) == 1, label
    # #209: Working with me holds the skill notes.
    assert {name: value[1:] for name, value in sections.items() if value[0]} == {
        name: (1, "system")
        for name in ("looking_for", "ruled_out", "facts", "writing", "working_with_me")
    }

    # Writing rules gather the policy's instructions and the template statements.
    writing = preferences(path)["writing"][0]
    assert [item["scope"] for item in writing] == [
        "all",
        "letter",
        "cv",
        "all",
        "all",
        "letter",
        "letter",
    ]
    general = json.loads(
        query(pre_upgrade, "SELECT data FROM settings WHERE key='instructions'")[0][0]
    )["general"]
    assert writing[4]["text"] == general
    assert writing[5:] == [
        {
            "text": "Opening: Name the role and one result that fits it. (from template "
            "Synthetic letter)",
            "scope": "letter",
        },
        {"text": "No links in the body. (from template Synthetic letter)", "scope": "letter"},
    ]
    # The template keeps its limits and other settings; the instructions setting is gone.
    rules = query(path, "SELECT rules FROM templates WHERE name='Synthetic letter'")[0][0]
    assert json.loads(rules) == {"date_format": "MMM YYYY", "engine": "lualatex", "max_pages": 1}
    assert query(path, "SELECT count(*) FROM settings WHERE key='instructions'") == [(0,)]

    # The archive keeps the policy whole.
    archive = json.loads(archive_path.read_text())
    policy = archive["policy"]
    assert len(policy["items"]) == 15 and len(policy["sections"]) == 4
    assert {item["id"] for item in policy["items"]} == {
        row[0] for row in query(pre_upgrade, "SELECT id FROM policy_items")
    }
    assert [row["key"] for row in policy["general_instructions"]] == ["instructions"]
    assert [row["name"] for row in policy["template_rules"]] == ["Synthetic letter"]
    assert "statements" in json.loads(policy["template_rules"][0]["rules"])
    dropped = archive["dropped_columns"]
    assert len(dropped["jobs.dismissed_rule_id"]) == len(dropped["jobs.dismissed_rule_label"]) == 2
    assert len(dropped["job_signals.rules"]) == 2
    assert "context_inputs.policy" not in dropped and "policy_items" not in archive.get(
        "dropped_tables", {}
    )


def test_rule_dismissals_are_kept_with_the_rule_as_reason(upgraded):
    path, pre_upgrade = upgraded[:2]
    before = query(
        pre_upgrade,
        f"SELECT id,dismissed_rule_label,dismissed_reason,{LABEL.format('dismissed_by')} "
        "FROM jobs WHERE dismissed_rule_id IS NOT NULL ORDER BY id",
    )
    assert before and all(reason == "" for _, _, reason, _ in before)
    after = query(
        path,
        "SELECT id,dismissed_reason,dismissed_by,triage FROM jobs WHERE id IN "
        f"({','.join('?' for _ in before)}) ORDER BY id",
        [row[0] for row in before],
    )
    assert after == [(job, label, by, "dismissed") for job, label, _, by in before]
    assert query(
        path, "SELECT dismissed_reason FROM jobs WHERE dismissed_reason<>'' ORDER BY id"
    ) == (
        query(
            pre_upgrade,
            "SELECT CASE WHEN dismissed_reason='' THEN dismissed_rule_label ELSE dismissed_reason "
            "END FROM jobs WHERE dismissed_reason<>'' OR dismissed_rule_label IS NOT NULL ORDER BY id",
        )
    )


def _sentences(count, start=0):
    return " ".join(
        f"Synthetic rule {n} keeps letters short and specific." for n in range(start, start + count)
    )


def test_split_text_keeps_whole_paragraphs_sentences_and_words_in_order():
    short = "A short paragraph that fits."
    long_paragraph = _sentences(60)  # about 3,000 characters, sentences of 50
    one_long_sentence = " ".join(["word"] * 900)  # 4,499 characters without a full stop
    text = f"{short}\n\n{long_paragraph}\n\n{one_long_sentence}"
    pieces = m15.split_text(text)
    assert all(0 < len(piece) <= m15.PREFERENCE_ITEM_LIMIT for piece in pieces)
    # Nothing is lost or reordered, and no word is cut.
    assert " ".join(pieces).split() == text.split()
    # The short paragraph travels with the first sentences; sentences stay whole.
    assert pieces[0].startswith(short + "\n\nSynthetic rule 0 ")
    assert all(piece.endswith(".") for piece in pieces[:2])
    assert m15.split_text("Fits.") == ["Fits."] and m15.split_text("  ") == []


def test_long_preference_texts_become_several_items_within_the_limit(tmp_path):
    instructions = json.dumps({"general": _sentences(100)})
    note = _sentences(50, start=100)
    path = load_fixture(
        tmp_path / "openings.sqlite",
        f"UPDATE settings SET data='{instructions}' WHERE key='instructions'; "
        f"UPDATE policy_items SET note='{note}' WHERE label='Work authorization';",
    )
    # Before the upgrade: two texts are too long, and they split into five items.
    with closing(sqlite3.connect("file::memory:", uri=True)) as conn:
        conn.executescript(m15.SCHEMA_SQL.read_text())
        conn.execute("ATTACH DATABASE ? AS old", (path.resolve().as_uri() + "?mode=ro",))
        statements = m15.preference_statements(conn)[0].values()
        every = [item["text"] for items in statements for item in items]
    pieces = [m15.split_text(text) for text in every if len(text) > m15.PREFERENCE_ITEM_LIMIT]
    assert len(pieces) == 2 and sum(len(split) for split in pieces) == 5
    Database(path)
    sections = preferences(path)
    every = [item for section in sections.values() for item in section[0]]
    assert every and all(len(item["text"]) <= m15.PREFERENCE_ITEM_LIMIT for item in every)
    writing = [item for item in sections["writing"][0] if "Synthetic rule" in item["text"]]
    assert len(writing) == 3 and {item["scope"] for item in writing} == {"all"}
    assert " ".join(item["text"] for item in writing).split() == _sentences(100).split()
    facts = [item["text"] for item in sections["facts"][0]]
    start = next(i for i, text in enumerate(facts) if text.startswith("Work authorization"))
    held = " ".join(facts[start : start + 2])
    assert held.endswith(note) and len(facts[start]) <= m15.PREFERENCE_ITEM_LIMIT


def test_a_workspace_without_policy_items_keeps_the_default_writing_rule(tmp_path):
    path = load_fixture(
        tmp_path / "openings.sqlite",
        "DELETE FROM policy_items; DELETE FROM settings WHERE key='instructions'; "
        "UPDATE templates SET rules='{}';",
    )
    Database(path)
    sections = preferences(path)
    assert [len(sections[name][0]) for name in ("looking_for", "facts", "writing")] == [
        0,
        1,
        1,
    ]  # #209: the answered question
    assert sections["writing"][0][0]["text"].startswith("Use only the supplied career evidence.")
    assert query(path, "SELECT count(*) FROM settings WHERE key='workspace'") == [(0,)]


# #209 Remove the agent-collaboration layer; minimal attribution.

# The actor label of a schema-14 actor block, computed independently of the migration.
LABEL = (
    "CASE WHEN {0}_kind IS NULL THEN NULL "
    "WHEN {0}_kind='token' AND {0}_token_kind='agent' THEN 'agent:'||{0}_name "
    "WHEN {0}_kind='token' THEN 'owner' ELSE {0}_kind END"
)


def test_every_actor_block_becomes_its_label_and_a_former_run_one_batch(tmp_path, upgraded):
    path, pre_upgrade = upgraded[:2]
    for table, new_table, new, old in (
        ("events", "events", "actor", "actor"),
        ("notes", "notes", "author", "author"),
        ("jobs", "jobs", "dismissed_by", "dismissed_by"),
        ("responses", "replies", "created_by", "created_by"),
        ("responses", "replies", "updated_by", "updated_by"),
    ):
        before = query(pre_upgrade, f"SELECT id,{LABEL.format(old)} FROM {table} ORDER BY 1")
        after = dict(query(path, f"SELECT id,{new} FROM {new_table}"))
        assert {row[0]: after[row[0]] for row in before} == dict(before), (table, new)
    labels = {row[0] for row in query(path, "SELECT DISTINCT actor FROM events")}
    assert labels == {"owner", "system", "agent:career-agent", "agent:synthetic-agent-probe"}
    # A token of the owner and a token from before 0.17 are the owner; no kind is no label.
    changed = load_fixture(
        tmp_path / "kinds.sqlite",
        "UPDATE events SET actor_kind='token',actor_token_kind=NULL,actor_name='script' "
        "WHERE rowid=(SELECT min(rowid) FROM events WHERE actor_kind='owner');"
        "UPDATE events SET actor_kind=NULL WHERE rowid=(SELECT min(rowid) FROM events "
        "WHERE actor_kind='system');",
    )
    Database(changed)
    assert query(changed, "SELECT count(*) FROM events WHERE actor IS NULL") == [(1,)]
    assert query(changed, "SELECT count(*) FROM events WHERE actor='owner'") == [(42,)]
    # The token columns stay in the archive.
    dropped = json.loads(m15.files(changed).archive.read_text())["dropped_columns"]
    assert any(item["value"] == "script" for item in dropped["events.actor_name"])
    # The changes of a former run share one batch.
    before = query(pre_upgrade, "SELECT id,run_id FROM events WHERE run_id IS NOT NULL ORDER BY id")
    after = query(path, "SELECT id,batch_id FROM events WHERE batch_id IS NOT NULL ORDER BY id")
    assert before and after == [(event, "run:" + run) for event, run in before]
    assert query(path, "SELECT count(*) FROM pragma_table_info('events') WHERE name='run_id'") == [
        (0,)
    ]


def test_runs_questions_requests_and_skill_notes_are_archived_and_kept_where_the_owner_looks(
    upgraded,
):
    path, pre_upgrade, archive_path = upgraded[:3]
    archive = json.loads(archive_path.read_text())
    for table in ("runs", "questions", "requests", "skill_notes"):
        with closing(sqlite3.connect(pre_upgrade)) as conn:
            conn.row_factory = sqlite3.Row
            rows = [dict(row) for row in conn.execute(f"SELECT * FROM {table}")]
        assert rows and archive["counts"][table] == len(rows) == len(archive[table])
        key = ("skill", "version") if table == "skill_notes" else ("id",)
        by_key = {tuple(item[k] for k in key): item for item in archive[table]}
        for row in rows:
            assert by_key[tuple(row[k] for k in key)] == row
        assert query(path, f"SELECT count(*) FROM sqlite_master WHERE name='{table}'") == [(0,)]
    # Run reports and change counts are kept as stored.
    finished = [run for run in archive["runs"] if run["status"] == "finished"]
    assert finished and all(json.loads(run["report"])["summary"] for run in finished)
    assert "dropped_tables" not in archive or not set(archive["dropped_tables"]) & {
        "runs",
        "questions",
        "requests",
        "skill_notes",
    }

    # Answers, requests and skill notes stay where the owner looks.
    created = query(
        path,
        "SELECT job_id,application_id,body,author,created_at FROM notes WHERE id NOT IN "
        f"({','.join(repr(row[0]) for row in query(pre_upgrade, 'SELECT id FROM notes'))})",
    )
    request = query(
        pre_upgrade,
        "SELECT r.application_id,a.job_id,r.text,r.result,r.created_at FROM requests r "
        "JOIN applications a ON a.id=r.application_id",
    )[0]
    assert created == [
        (
            request[1],
            request[0],
            f"Request to the agent ({request[4][:10]}, done): {request[2]} — Result: {request[3]}",
            "system",
            request[4],
        )
    ]
    # The answered question without a subject is a fact; open and withdrawn ones are not.
    question, answer, asked, answered = query(
        pre_upgrade,
        "SELECT question,answer,created_at,resolved_at FROM questions WHERE state='answered'",
    )[0]
    facts = texts(path, "facts")
    assert facts[-1] == (
        f"Question from agent:career-agent ({asked[:10]}): {question} — "
        f"Answer ({answered[:10]}): {answer}"
    )
    for (text,) in query(pre_upgrade, "SELECT question FROM questions WHERE state<>'answered'"):
        assert not any(text in item for item in facts)
    # The current version of each skill's notes is one Working with me item.
    current = query(
        pre_upgrade, "SELECT skill,text FROM skill_notes ORDER BY version DESC LIMIT 1"
    )[0]
    assert texts(path, "working_with_me") == [f"For {current[0]}: {current[1]}"]


def test_answers_about_jobs_and_applications_become_notes_on_them(tmp_path):
    path = load_fixture(
        tmp_path / "openings.sqlite",
        "UPDATE questions SET state='answered',answer='Yes.',answer_choice=NULL,"
        "resolved_at='2026-11-13T10:00:00+00:00' WHERE subject_type IN ('job','application');"
        "INSERT INTO idempotency_keys(scope,key,fingerprint,record_id,created_at) "
        "VALUES('runs','k1','f','r','2026-11-13T10:00:00+00:00'),"
        "('notes','k2','f','n','2026-11-13T10:00:00+00:00');",
    )
    with closing(sqlite3.connect(path)) as conn:
        asked = conn.execute(
            "SELECT q.question,coalesce(q.job_id,a.job_id),q.application_id FROM questions q "
            "LEFT JOIN applications a ON a.id=q.application_id "
            "WHERE q.subject_type IN ('job','application') ORDER BY q.subject_type"
        ).fetchall()
    Database(path)
    notes = query(
        path,
        "SELECT job_id,application_id,body FROM notes WHERE author='system' AND body LIKE "
        "'Question from %' ORDER BY application_id IS NULL",
    )
    assert [(job, application) for job, application, _ in notes] == [
        (row[1], row[2]) for row in asked
    ]
    for (_, _, body), row in zip(notes, asked, strict=True):
        assert row[0] in body and body.endswith("Answer (2026-11-13): Yes.")
    # The idempotency keys of removed records go to the archive with them.
    assert query(path, "SELECT scope FROM idempotency_keys") == [("notes",)]
    archive = json.loads(m15.files(path).archive.read_text())
    assert [row["key"] for row in archive["idempotency_keys_of_removed"]] == ["k1"]


# #215 Frozen contexts, snapshots and staleness.

CONTEXT_OBJECTS = (
    "SELECT name FROM sqlite_master WHERE name LIKE '%context%' OR name LIKE 'snapshot%' "
    "OR name='all_files'"
)


def test_no_context_object_remains_and_the_archive_keeps_contexts_by_part_hash(upgraded):
    path, pre_upgrade, archive_path = upgraded[:3]
    assert query(path, CONTEXT_OBJECTS) == []
    for table in ("documents", "files"):
        columns = {row[1] for row in query(path, f"PRAGMA table_info({table})")}
        assert not {"context_id", "legacy_content"} & columns
    # Every revision keeps its files, hashes, text, cited ids and revision chain.
    revisions = (
        "SELECT d.id,d.previous_id,d.kind,d.text,d.claim_ids,d.knowledge_ids,f.id,f.sha256,"
        "f.name,f.size,b.size FROM documents d LEFT JOIN files f ON f.document_id=d.id "
        "LEFT JOIN blobs b ON b.sha256=f.sha256 ORDER BY d.id,f.id"
    )
    kinds = {"resume": "cv", "cover_letter": "letter"}
    assert query(path, revisions) == [
        (*row[:2], kinds.get(row[2], row[2]), *row[3:]) for row in query(pre_upgrade, revisions)
    ]
    assert query(pre_upgrade, "SELECT count(*) FROM documents WHERE context_id IS NOT NULL")[0][0]

    # The archive keeps the contexts by part hash.
    archive = json.loads(archive_path.read_text())
    contexts = {row["id"]: row for row in archive["contexts"]}
    assert set(contexts) == {row[0] for row in query(pre_upgrade, "SELECT id FROM contexts")}
    parts = {(row["kind"], row["hash"]): row for row in archive["snapshot_parts"]}
    # Each part once, by hash; the archive holds no expanded payload.
    assert (
        len(parts)
        == len(archive["snapshot_parts"])
        == query(pre_upgrade, "SELECT count(*) FROM snapshot_parts")[0][0]
    )

    def payload(context):
        """The context's payload text, rebuilt from the archive alone."""
        literals, out = json.loads(context["frame"]), []
        references = [ref for ref in json.loads(context["parts"]) if ref["position"] >= 0]
        out.append(literals[0])
        for reference, literal in zip(references, literals[1:], strict=True):
            part = parts[(reference["kind"], reference["hash"])]
            if part["kind"] == "list":
                text = ",".join(parts[("text", h)]["content"] for h in json.loads(part["items"]))
            elif part["kind"] == "asset":
                file_id = reference["file_id"]
                text = (
                    f'{{"id":"{file_id}",{part["content"][1:-1]},'
                    f'"url":"/api/v1/files/{file_id}/content"}}'
                )
            else:
                text = part["content"]
            out.append(text + literal)
        return "".join(out)

    for context in contexts.values():
        rebuilt = payload(context)
        assert hashlib.sha256(rebuilt.encode()).hexdigest() == context["signature"]
    files = query(
        pre_upgrade,
        "SELECT context_id,file_id FROM context_parts WHERE file_id IS NOT NULL ORDER BY 1,2",
    )
    assert files
    assert [(row["context_id"], row["id"]) for row in archive["context_files"]] == files
    assert all(row["sha256"] and row["size"] for row in archive["context_files"])
    assert archive["legacy_content"] == dict(
        query(
            pre_upgrade, "SELECT id,legacy_content FROM documents WHERE legacy_content IS NOT NULL"
        )
    )
    assert archive["dropped_columns"]["documents.context_id"]
    assert "documents.legacy_content" not in archive["dropped_columns"]
    assert "dropped_tables" not in archive


def test_bytes_only_contexts_referenced_are_left_in_the_pre_upgrade_copy(tmp_path, caplog):
    # Without the template's own files, its frozen copies are the only references.
    path = load_fixture(
        tmp_path / "openings.sqlite",
        "DELETE FROM files WHERE sha256 IN (SELECT blob FROM snapshot_parts) "
        "AND template_id IS NOT NULL;"
        "INSERT INTO blobs(sha256,content,size) VALUES('f'||hex(randomblob(31)),x'00ff',2);"
        "INSERT INTO files(id,sha256,name,size,context_id,created_at) SELECT 'legacy-file',"
        "sha256,'old.bin',2,(SELECT min(id) FROM contexts),'2026-01-01' FROM blobs WHERE size=2;",
    )
    only = query(path, CONTEXT_ONLY_BLOBS)[0][0]
    dropped = query(
        path,
        "SELECT total(size) FROM blobs b WHERE " + CONTEXT_ONLY_BLOBS.split(" WHERE ", 1)[1],
    )[0][0]
    before = query(path, "SELECT total(length(content)) FROM blobs")[0][0]
    assert only >= 2 and dropped > 2
    with caplog.at_level("WARNING", logger=m15.LOG.name):
        Database(path)
    pre_upgrade = m15.files(path).pre_upgrade
    after = query(path, "SELECT total(length(content)) FROM blobs")[0][0]
    assert after == before - dropped
    assert query(
        path,
        "SELECT count(*) FROM blobs b WHERE NOT EXISTS(SELECT 1 FROM files f "
        "WHERE f.sha256=b.sha256)",
    ) == [(0,)]
    assert f"leaves out {int(dropped)} bytes" in caplog.text
    archive = json.loads(m15.files(path).archive.read_text())
    legacy = [row for row in archive["context_files"] if row["id"] == "legacy-file"]
    assert legacy and legacy[0]["name"] == "old.bin"
    assert query(pre_upgrade, "SELECT total(length(content)) FROM blobs")[0][0] == before


# #211 Trim secondary features.


def test_claim_role_and_group_fold_into_metadata_and_the_archive(tmp_path):
    path = load_fixture(
        tmp_path / "openings.sqlite",
        # A key the owner already set is kept; the value goes to the archive.
        """UPDATE claims SET metadata='{"group":"Mine","source":"synthetic"}'
        WHERE id=(SELECT min(id) FROM claims WHERE role='core');""",
    )
    before = {
        row[0]: row[1:]
        for row in query(path, 'SELECT id,role,"group",default_in_cv,metadata FROM claims')
    }
    Database(path)
    pre_upgrade = m15.files(path).pre_upgrade
    assert query(
        path,
        "SELECT count(*) FROM pragma_table_info('claims') WHERE name IN "
        "('role','group','default_in_cv')",
    ) == [(0,)]
    after = {
        row[0]: row[1:] for row in query(path, "SELECT id,always_include,metadata FROM claims")
    }
    assert set(after) == set(before)
    conflicts = set()
    for claim_id, (role, group, in_cv, metadata) in before.items():
        always, folded = after[claim_id]
        assert always == in_cv
        expected = json.loads(metadata)
        for key, value, default in (("role", role, "supporting"), ("group", group, "")):
            if value != default:
                if key in expected:
                    conflicts.add(claim_id)
                else:
                    expected[key] = value
        assert json.loads(folded) == expected, claim_id
    assert len(conflicts) == 1
    archive = json.loads(m15.files(path).archive.read_text())
    fields = archive["claim_fields"]
    assert {row["id"]: (row["role"], row["group"]) for row in fields} == {
        claim_id: (role, group)
        for claim_id, (role, group, _, _) in before.items()
        if role != "supporting" or group
    }
    assert {row["id"] for row in fields if row["conflict"]} == conflicts
    assert archive["counts"]["claim_fields"] == len(fields) == 8
    assert not any(key.startswith("claims.") for key in archive.get("dropped_columns", {}))
    assert query(pre_upgrade, "SELECT count(*) FROM claims WHERE default_in_cv=1") == [(4,)]


# Archive.


def test_the_archive_holds_every_dropped_value_with_the_counts_of_its_source(upgraded):
    path, pre_upgrade, archive_path = upgraded[:3]
    assert stat.S_IMODE(archive_path.stat().st_mode) == 0o600
    archive = json.loads(archive_path.read_text())
    assert (archive["format"], archive["from_schema"], archive["to_schema"]) == (
        "openings-archive",
        14,
        15,
    )
    dropped = archive["dropped_columns"]
    for table, column, condition in (
        ("applications", "idempotency_key", "idempotency_key IS NOT NULL"),
        ("responses", "estimated", "estimated<>0"),
        ("responses", "origin", "origin<>'manual'"),
        ("notes", "origin", "origin<>'manual'"),
    ):
        rows = query(pre_upgrade, f"SELECT id,{column} FROM {table} WHERE {condition}")
        assert rows, (table, column)
        key = f"{table}.{column}"
        assert sorted((item["id"], item["value"]) for item in dropped[key]) == sorted(rows)
        assert archive["counts"]["dropped_columns." + key] == len(rows)
    assert {key for key in archive["counts"] if key.startswith("dropped_columns.")} == {
        f"dropped_columns.{sub}" for sub in dropped
    }

    # Welcome languages leave the signals for the archive.
    welcome = query(
        pre_upgrade, "SELECT job_id,welcome FROM job_signals WHERE welcome<>'[]' ORDER BY job_id"
    )
    assert welcome
    assert [(row["job_id"], row["welcome"]) for row in archive["job_signals_welcome"]] == welcome
    assert "job_signals.welcome" not in archive.get("dropped_columns", {})
    columns = "job_id,format,language,language_confidence,required,duplicate_of,distinct_from"
    sql = f"SELECT {columns} FROM job_signals ORDER BY job_id"
    assert query(path, sql) == query(pre_upgrade, sql)


def test_a_backup_of_the_previous_schema_is_restored_upgraded(tmp_path):
    backup = load_fixture(tmp_path / "upload.sqlite")
    before = digest(backup)
    workspace = Workspace(tmp_path / "data" / "openings.sqlite")
    assert restore_database(workspace, backup)["restored"]
    assert digest(backup) == before
    # Restore keeps the destination's tokens and drops transfer grants.
    restored, uploaded = counts(workspace.db.path), expected_counts(counts(backup), backup)
    for name in ("api_tokens", "transfer_grants"):
        restored.pop(name), uploaded.pop(name)
    assert restored == uploaded
    archives = list((tmp_path / "data").glob("openings.pre-0.24-archive-restored-*.json"))
    assert len(archives) == 1 and json.loads(archives[0].read_text())["counts"]


# Interruptions and refusals.


def test_a_stop_between_the_two_renames_is_finished_at_the_next_start(tmp_path, monkeypatch):
    path = load_fixture(tmp_path / "openings.sqlite")
    before, original = digest(path), counts(path)
    calls = []

    def replace(source, target):
        calls.append(target)
        if len(calls) == 2:
            raise Killed
        m15.os.replace(source, target)

    monkeypatch.setattr(m15, "_replace", replace)
    with pytest.raises(Killed):
        Database(path)
    files = m15.files(path)
    assert not path.exists() and files.next.exists() and files.pre_upgrade.exists()
    monkeypatch.undo()
    Database(path)
    assert counts(path) == expected_counts(original, files.pre_upgrade)
    assert digest(files.pre_upgrade) == before
    assert not files.next.exists()


def test_a_stop_before_the_swap_leaves_the_original_and_runs_again(tmp_path, monkeypatch):
    path = load_fixture(tmp_path / "openings.sqlite")
    before, original = digest(path), counts(path)

    def stop(*args):
        raise Killed

    monkeypatch.setattr(m15, "_verify", stop)
    with pytest.raises(Killed):
        Database(path)
    files = m15.files(path)
    assert digest(path) == before and files.next.exists()
    monkeypatch.undo()
    Database(path)
    assert counts(path) == expected_counts(original, files.pre_upgrade)
    assert digest(files.pre_upgrade) == before
    assert not files.next.exists()


def unchanged_after_refusal(path, before):
    files = m15.files(path)
    assert digest(path) == before
    assert not files.next.exists() and not files.archive.exists()
    assert not files.pre_upgrade.exists()


def test_a_refused_start_writes_nothing(tmp_path, monkeypatch):
    path = load_fixture(tmp_path / "openings.sqlite")
    before = digest(path)
    # A failed check removes the new file and keeps the original.
    with monkeypatch.context() as patch:
        patch.setattr(m15, "INVARIANTS", (("an impossible value", "SELECT 1", "SELECT 2"),))
        with pytest.raises(DomainError) as refused:
            Database(path)
    assert refused.value.code == "upgrade_failed"
    assert "an impossible value: 1 instead of 2" in refused.value.message
    unchanged_after_refusal(path, before)

    # Without room the start is refused.
    usage = m15.shutil.disk_usage(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(m15.shutil, "disk_usage", lambda _: usage._replace(free=1024))
        with pytest.raises(DomainError) as refused:
            Database(path)
    assert (refused.value.status, refused.value.code) == (507, "upgrade_room")
    assert refused.value.details["needed_bytes"] > 2.2 * path.stat().st_size
    unchanged_after_refusal(path, before)

    # Other schemas are refused unchanged.
    for version, words in (
        (13, "older than 0.23. Open it once with the 0.23 image"),
        (16, "newer Openings"),
    ):
        other = load_fixture(
            tmp_path / f"schema-{version}.sqlite", f"PRAGMA user_version={version};"
        )
        digest_before = digest(other)
        with pytest.raises(DomainError) as refused:
            Database(other)
        assert refused.value.code == "schema_version" and words in refused.value.message
        unchanged_after_refusal(other, digest_before)

    # So is the database of another program: no schema version, tables of its own.
    unrelated = tmp_path / "unrelated.sqlite"
    with closing(sqlite3.connect(unrelated)) as conn:
        conn.execute("CREATE TABLE jobs (old_field TEXT)")
        conn.execute("INSERT INTO jobs VALUES ('retained')")
        conn.commit()
    digest_before = digest(unrelated)
    with pytest.raises(DomainError):
        Workspace(unrelated)
    unchanged_after_refusal(unrelated, digest_before)
