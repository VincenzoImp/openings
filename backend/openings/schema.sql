-- Schema 15: the whole layout of a new workspace. It runs once, on a new file;
-- an older workspace is copied into a file created from it (migrations/m15.py),
-- so an upgraded workspace has exactly these objects.
CREATE TABLE settings (
 key TEXT PRIMARY KEY, data TEXT NOT NULL CHECK(json_valid(data)), version INTEGER NOT NULL DEFAULT 1,
 updated_at TEXT NOT NULL
);
CREATE TABLE api_tokens (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL, last_used_at TEXT,
 kind TEXT NOT NULL DEFAULT 'owner' CHECK(kind IN ('owner','agent'))
);
CREATE TABLE jobs (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, company TEXT NOT NULL, location TEXT NOT NULL DEFAULT '',
 url TEXT NOT NULL DEFAULT '', posting TEXT NOT NULL DEFAULT '', triage TEXT NOT NULL DEFAULT 'new'
 CHECK(triage IN ('new','shortlisted','dismissed')),
 metadata TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(metadata)), overrides TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(overrides)),
 content_version INTEGER NOT NULL DEFAULT 1, version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 -- The current dismissal: when, by whom and why. Cleared on restore.
 dismissed_at TEXT, dismissed_by_kind TEXT, dismissed_by_id TEXT, dismissed_by_name TEXT,
 dismissed_by_token_kind TEXT, dismissed_reason TEXT NOT NULL DEFAULT ''
);
CREATE INDEX jobs_url ON jobs(url);
CREATE INDEX jobs_triage ON jobs(triage,created_at);
-- The default order of the jobs list.
CREATE INDEX jobs_created ON jobs(created_at DESC,id);
CREATE VIRTUAL TABLE jobs_fts USING fts5(title,company,posting,content='jobs',content_rowid='rowid');
CREATE TRIGGER jobs_ai AFTER INSERT ON jobs BEGIN
 INSERT INTO jobs_fts(rowid,title,company,posting) VALUES(new.rowid,new.title,new.company,new.posting); END;
CREATE TRIGGER jobs_ad AFTER DELETE ON jobs BEGIN
 INSERT INTO jobs_fts(jobs_fts,rowid,title,company,posting) VALUES('delete',old.rowid,old.title,old.company,old.posting); END;
CREATE TRIGGER jobs_au AFTER UPDATE OF title,company,posting ON jobs BEGIN
 INSERT INTO jobs_fts(jobs_fts,rowid,title,company,posting) VALUES('delete',old.rowid,old.title,old.company,old.posting);
 INSERT INTO jobs_fts(rowid,title,company,posting) VALUES(new.rowid,new.title,new.company,new.posting); END;
CREATE TABLE sources (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, config TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(config)),
 enabled INTEGER NOT NULL DEFAULT 0, schedule TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(schedule)), version INTEGER NOT NULL DEFAULT 1,
 last_run_at TEXT, last_scheduled_at TEXT, last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE postings (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 source_id TEXT REFERENCES sources(id) ON DELETE SET NULL, identity TEXT NOT NULL UNIQUE,
 url TEXT NOT NULL DEFAULT '', payload TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(payload)), content_hash TEXT NOT NULL,
 first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
 -- Set when a complete run of a company board no longer listed this posting;
 -- cleared when it is seen again.
 unlisted_at TEXT
);
CREATE INDEX postings_job ON postings(job_id);
CREATE TABLE job_identities (
 identity TEXT NOT NULL, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 PRIMARY KEY(identity,job_id)
) WITHOUT ROWID;
CREATE INDEX job_identities_job ON job_identities(job_id);
CREATE TABLE posting_details (
 identity TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 checked_at TEXT NOT NULL
);
CREATE INDEX posting_details_job ON posting_details(job_id);
-- concluded_on is the day an application closed as no_response was concluded.
-- required_documents lists the document kinds Ready needs (workspace/readiness.py);
-- from_shortlist marks an application a job's shortlist started, which undoing the
-- shortlist removes while it is empty.
CREATE TABLE applications (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 status TEXT NOT NULL DEFAULT 'shortlisted' CHECK(status IN ('shortlisted','applied','interview','offer','closed')),
 outcome TEXT CHECK(outcome IS NULL OR outcome IN ('accepted','rejected','not_pursued','no_response')),
 questions TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(questions)),
 answers TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(answers)),
 version INTEGER NOT NULL DEFAULT 1, applied_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 priority INTEGER CHECK(priority IS NULL OR priority BETWEEN 1 AND 5),
 deadline TEXT CHECK(deadline IS NULL OR (length(deadline)=10 AND date(deadline)=deadline)),
 requirements TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(requirements) AND json_type(requirements)='array'),
 concluded_on TEXT CHECK(concluded_on IS NULL OR (length(concluded_on)=10 AND date(concluded_on)=concluded_on)),
 required_documents TEXT NOT NULL DEFAULT '["cv","letter"]'
  CHECK(required_documents IN ('["cv","letter"]','["cv"]','["letter"]','[]')),
 from_shortlist INTEGER NOT NULL DEFAULT 0 CHECK(from_shortlist IN (0,1))
);
-- An agent run: opened by an API token, closed with a stored report.
CREATE TABLE runs (
 id TEXT PRIMARY KEY, token_id TEXT NOT NULL, token_name TEXT NOT NULL,
 workflow TEXT NOT NULL, scope TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','finished','interrupted')),
 note TEXT NOT NULL DEFAULT '', report TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(report)),
 change_counts TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(change_counts)),
 superseded_by TEXT, version INTEGER NOT NULL DEFAULT 1,
 started_at TEXT NOT NULL, last_activity_at TEXT NOT NULL, ended_at TEXT, updated_at TEXT NOT NULL,
 token_kind TEXT
);
-- One record per change. job_id/application_id keep the owning timeline (and its
-- deletion); subject_* names the changed record of any type; actor_* and run_id
-- say who changed it (a token with its kind, owner or agent). Rows written before
-- 0.17 have no actor.
CREATE TABLE events (
 id TEXT PRIMARY KEY, job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE,
 application_id TEXT REFERENCES applications(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(payload)), created_at TEXT NOT NULL,
 subject_type TEXT, subject_id TEXT, actor_kind TEXT, actor_id TEXT, actor_name TEXT,
 actor_token_kind TEXT, run_id TEXT REFERENCES runs(id) ON DELETE SET NULL
);
CREATE INDEX events_app ON events(application_id,created_at);
-- A note on a job, or on one application when application_id is set (its scope).
-- author_* and run_id say who wrote it; pinned_at marks the one pinned note of
-- its scope.
CREATE TABLE notes (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 application_id TEXT REFERENCES applications(id) ON DELETE CASCADE, body TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 author_kind TEXT, author_id TEXT, author_name TEXT, author_token_kind TEXT,
 run_id TEXT REFERENCES runs(id) ON DELETE SET NULL, pinned_at TEXT
);
CREATE TABLE knowledge (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, organization TEXT NOT NULL DEFAULT '',
 dates TEXT CHECK(dates IS NULL OR json_valid(dates)), skills TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(skills)),
 position INTEGER NOT NULL DEFAULT 0 CHECK(position>=0), narrative TEXT NOT NULL DEFAULT '',
 metadata TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(metadata)), version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE claims (
 id TEXT PRIMARY KEY, knowledge_id TEXT NOT NULL REFERENCES knowledge(id) ON DELETE CASCADE,
 text TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0, position INTEGER NOT NULL DEFAULT 0 CHECK(position>=0),
 metadata TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(metadata)),
 version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 -- Typed selection fields: in the CV unless the job says otherwise, how
 -- strongly the claim is preferred, and a free short group name.
 default_in_cv INTEGER NOT NULL DEFAULT 0 CHECK(default_in_cv IN (0,1)),
 role TEXT NOT NULL DEFAULT 'supporting' CHECK(role IN ('core','supporting','bench')),
 "group" TEXT NOT NULL DEFAULT ''
);
CREATE TABLE templates (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('cv','letter')),
 tex TEXT NOT NULL DEFAULT '', guidance TEXT NOT NULL DEFAULT '', rules TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(rules)),
 is_default INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX templates_default ON templates(kind) WHERE is_default=1;
CREATE TABLE contexts (
 id TEXT PRIMARY KEY, application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
 signature TEXT NOT NULL, created_at TEXT NOT NULL,
 -- The payload is rebuilt from frame literals and context_parts (snapshots.py); the
 -- other columns summarise it for lists.
 frame TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(frame)), job_title, company, note_preview, knowledge_count INTEGER,
 claim_count INTEGER, template_name, file_count INTEGER NOT NULL DEFAULT 0
);
-- Derived from immutable contexts: the input versions each context froze. Rebuildable.
CREATE TABLE context_inputs (
 context_id TEXT PRIMARY KEY REFERENCES contexts(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL, profile_version INTEGER,
 templates TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(templates)),
 knowledge TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(knowledge)),
 claims TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(claims)),
 -- Short hashes of the parts it froze: Profile parts, Preferences statements and
 -- template contents, compared by staleness.py. Derived from the payload.
 parts TEXT CHECK(parts IS NULL OR json_valid(parts))
);
-- A document revision. A CV or letter (cv, letter) is its PDF and optional .tex
-- source (files): it is complete once its PDF is stored. content stays '{}'; text is
-- the readable text, from the source (text_from 'tex', documents/text.py) or else
-- from the PDF ('pdf', documents/pdf.py), NULL when none could be read;
-- legacy_content keeps, read-only, the content such a revision had before 0.22.
-- Form answers and other kinds keep structured content. claim_ids and
-- knowledge_ids are the evidence it cites.
CREATE TABLE documents (
 id TEXT PRIMARY KEY, application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
 context_id TEXT REFERENCES contexts(id) ON DELETE CASCADE, kind TEXT NOT NULL,
 title TEXT NOT NULL DEFAULT '', content TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(content)),
 previous_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
 version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
 text TEXT, text_from TEXT CHECK(text_from IS NULL OR text_from IN ('tex','pdf')), legacy_content TEXT CHECK(legacy_content IS NULL OR json_valid(legacy_content)),
 note TEXT NOT NULL DEFAULT '',
 claim_ids TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(claim_ids) AND json_type(claim_ids)='array'),
 knowledge_ids TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(knowledge_ids) AND json_type(knowledge_ids)='array')
);
CREATE TABLE blobs (
 sha256 TEXT PRIMARY KEY, content BLOB NOT NULL, size INTEGER NOT NULL
);
CREATE TABLE files (
 id TEXT PRIMARY KEY, sha256 TEXT NOT NULL REFERENCES blobs(sha256), name TEXT NOT NULL,
 media_type TEXT NOT NULL DEFAULT 'application/octet-stream', size INTEGER NOT NULL,
 knowledge_id TEXT REFERENCES knowledge(id) ON DELETE CASCADE,
 template_id TEXT REFERENCES templates(id) ON DELETE CASCADE,
 context_id TEXT REFERENCES contexts(id) ON DELETE CASCADE,
 document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
 job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE, created_at TEXT NOT NULL,
 -- The SHA-256 of the source a revision's PDF was built from; NULL for every other
 -- file, for a PDF-only revision and for PDFs uploaded before 0.22.
 source_sha256 TEXT,
 CHECK((knowledge_id IS NOT NULL)+(template_id IS NOT NULL)+(context_id IS NOT NULL)+
       (document_id IS NOT NULL)+(job_id IS NOT NULL)=1)
);
CREATE TABLE transfer_grants (
 token_hash TEXT PRIMARY KEY, payload TEXT NOT NULL CHECK(json_valid(payload)), method TEXT NOT NULL,
 expires_at TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE collection_runs (
 id TEXT PRIMARY KEY, source_id TEXT REFERENCES sources(id) ON DELETE SET NULL,
 source_name TEXT NOT NULL, source_version INTEGER NOT NULL,
 source_snapshot TEXT NOT NULL CHECK(json_valid(source_snapshot)),
 overrides TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(overrides)), planned_at TEXT,
 created_at TEXT NOT NULL
);
CREATE INDEX collection_runs_source ON collection_runs(source_id,created_at);
CREATE TABLE tasks (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, source_id TEXT REFERENCES sources(id) ON DELETE SET NULL,
 run_id TEXT REFERENCES collection_runs(id) ON DELETE CASCADE,
 job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE, state TEXT NOT NULL DEFAULT 'queued',
 payload TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(payload)),
 result TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(result)), attempts INTEGER NOT NULL DEFAULT 0,
 dedupe_key TEXT UNIQUE, next_run_at TEXT NOT NULL, lease_until TEXT, lease_owner TEXT, error TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX tasks_run ON tasks(run_id);
CREATE INDEX tasks_due ON tasks(state,next_run_at);
CREATE TABLE providers (
 id TEXT PRIMARY KEY, policy TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(policy)),
 runtime TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(runtime)), version INTEGER NOT NULL DEFAULT 1,
 updated_at TEXT NOT NULL
);
CREATE INDEX applications_job ON applications(job_id,created_at DESC,id DESC);
CREATE UNIQUE INDEX applications_active_job ON applications(job_id) WHERE status<>'closed';
CREATE INDEX applications_status ON applications(status,updated_at);
CREATE INDEX applications_deadline ON applications(deadline);
CREATE INDEX documents_app ON documents(application_id,created_at);
CREATE INDEX documents_context ON documents(context_id);
CREATE INDEX contexts_app ON contexts(application_id,created_at);
CREATE INDEX files_document ON files(document_id);
CREATE INDEX files_context ON files(context_id);
CREATE INDEX files_template ON files(template_id);
CREATE INDEX files_knowledge ON files(knowledge_id);
CREATE INDEX claims_knowledge ON claims(knowledge_id);
CREATE INDEX documents_previous ON documents(previous_id);
CREATE INDEX events_job ON events(job_id);
CREATE INDEX events_created ON events(created_at);
CREATE INDEX notes_job ON notes(job_id,created_at);
CREATE INDEX notes_app ON notes(application_id);
CREATE INDEX files_job ON files(job_id);
CREATE INDEX files_blob ON files(sha256);
CREATE INDEX tasks_job ON tasks(job_id);
CREATE INDEX tasks_source ON tasks(source_id);
CREATE INDEX postings_source ON postings(source_id);
-- A question for the owner. The subject reference becomes NULL when its record is
-- deleted; subject_type and subject_label keep the question readable.
CREATE TABLE questions (
 id TEXT PRIMARY KEY, subject_type TEXT CHECK(subject_type IS NULL OR subject_type IN ('job','application','knowledge')),
 job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
 application_id TEXT REFERENCES applications(id) ON DELETE SET NULL,
 knowledge_id TEXT REFERENCES knowledge(id) ON DELETE SET NULL,
 subject_label TEXT NOT NULL DEFAULT '', question TEXT NOT NULL, why TEXT NOT NULL DEFAULT '',
 choices TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(choices) AND json_type(choices)='array'),
 state TEXT NOT NULL DEFAULT 'open' CHECK(state IN ('open','answered','withdrawn')),
 answer TEXT NOT NULL DEFAULT '', answer_choice TEXT,
 asked_by_kind TEXT NOT NULL, asked_by_id TEXT, asked_by_name TEXT, asked_by_token_kind TEXT,
 run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
 resolved_by_kind TEXT, resolved_by_id TEXT, resolved_by_name TEXT, resolved_by_token_kind TEXT,
 resolved_at TEXT,
 version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK((job_id IS NOT NULL)+(application_id IS NOT NULL)+(knowledge_id IS NOT NULL)<=1)
);
-- A request for the agent: an owner instruction read at the start of the next run.
-- Like a question, it outlives its subject through subject_type and subject_label.
CREATE TABLE requests (
 id TEXT PRIMARY KEY, subject_type TEXT CHECK(subject_type IS NULL OR subject_type IN ('job','application','knowledge')),
 job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
 application_id TEXT REFERENCES applications(id) ON DELETE SET NULL,
 knowledge_id TEXT REFERENCES knowledge(id) ON DELETE SET NULL,
 subject_label TEXT NOT NULL DEFAULT '', text TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'open' CHECK(state IN ('open','taken','done','declined','withdrawn')),
 result TEXT NOT NULL DEFAULT '',
 created_by_kind TEXT NOT NULL, created_by_id TEXT, created_by_name TEXT, created_by_token_kind TEXT,
 taken_by_kind TEXT, taken_by_id TEXT, taken_by_name TEXT, taken_by_token_kind TEXT, taken_at TEXT,
 run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
 resolved_by_kind TEXT, resolved_by_id TEXT, resolved_by_name TEXT, resolved_by_token_kind TEXT,
 resolved_at TEXT,
 version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK((job_id IS NOT NULL)+(application_id IS NOT NULL)+(knowledge_id IS NOT NULL)<=1)
);
CREATE UNIQUE INDEX runs_open_token ON runs(token_id) WHERE status='open';
CREATE INDEX runs_token ON runs(token_id,started_at);
CREATE INDEX runs_status ON runs(status,started_at);
CREATE INDEX runs_started ON runs(started_at);
CREATE INDEX events_run ON events(run_id,created_at);
CREATE INDEX events_subject ON events(subject_type,subject_id,created_at);
CREATE INDEX questions_state ON questions(state,created_at);
CREATE INDEX questions_resolved ON questions(state,resolved_at);
CREATE INDEX questions_job ON questions(job_id);
CREATE INDEX questions_application ON questions(application_id);
CREATE INDEX questions_knowledge ON questions(knowledge_id);
CREATE INDEX questions_run ON questions(run_id);
CREATE INDEX requests_state ON requests(state,created_at);
CREATE INDEX requests_created ON requests(created_at);
CREATE INDEX requests_updated ON requests(updated_at);
CREATE INDEX requests_job ON requests(job_id);
CREATE INDEX requests_application ON requests(application_id);
CREATE INDEX requests_knowledge ON requests(knowledge_id);
CREATE INDEX requests_run ON requests(run_id);
-- Content-addressed parts of frozen contexts; context files are served from them.
CREATE TABLE snapshot_parts (
 id INTEGER PRIMARY KEY, hash TEXT NOT NULL,
 kind TEXT NOT NULL DEFAULT 'text' CHECK(kind IN ('text','list','asset')),
 content TEXT NOT NULL, blob TEXT REFERENCES blobs(sha256),
 UNIQUE(hash,kind), CHECK((kind='asset')=(blob IS NOT NULL))
);
CREATE INDEX snapshot_parts_blob ON snapshot_parts(blob) WHERE blob IS NOT NULL;
CREATE TABLE snapshot_list_items (
 list_id INTEGER NOT NULL REFERENCES snapshot_parts(id) ON DELETE CASCADE,
 position INTEGER NOT NULL, part_id INTEGER NOT NULL REFERENCES snapshot_parts(id),
 PRIMARY KEY(list_id,position)
) WITHOUT ROWID;
CREATE INDEX snapshot_list_items_part ON snapshot_list_items(part_id);
CREATE TABLE context_parts (
 context_id TEXT NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
 position INTEGER NOT NULL, part_id INTEGER NOT NULL REFERENCES snapshot_parts(id),
 file_id TEXT, file_created_at TEXT,
 PRIMARY KEY(context_id,position)
) WITHOUT ROWID;
CREATE INDEX context_parts_part ON context_parts(part_id);
CREATE UNIQUE INDEX context_parts_file ON context_parts(file_id) WHERE file_id IS NOT NULL;
CREATE VIEW context_files AS
 SELECT cp.file_id AS id, p.blob AS sha256, json_extract(p.content,'$.path') AS name,
  json_extract(p.content,'$.media_type') AS media_type, json_extract(p.content,'$.size') AS size,
  NULL AS knowledge_id, NULL AS template_id, cp.context_id AS context_id,
  NULL AS document_id, NULL AS job_id, coalesce(cp.file_created_at,c.created_at) AS created_at,
  NULL AS source_sha256
 FROM context_parts cp JOIN snapshot_parts p ON p.id=cp.part_id JOIN contexts c ON c.id=cp.context_id
 WHERE cp.file_id IS NOT NULL;
CREATE VIEW all_files AS
 SELECT id,sha256,name,media_type,size,knowledge_id,template_id,context_id,document_id,job_id,created_at,source_sha256 FROM files
 UNION ALL SELECT id,sha256,name,media_type,size,knowledge_id,template_id,context_id,document_id,job_id,created_at,source_sha256 FROM context_files;
-- The owner's Preferences (preferences.py): five sections of statements in the
-- owner's words, each replaced whole with its own version. An item is
-- {"text": ...}, and in writing {"text": ..., "scope": "all"|"cv"|"letter"}.
-- updated_by is the actor label: owner, agent:<token name> or system.
CREATE TABLE preference_sections (
 section TEXT PRIMARY KEY CHECK(section IN ('looking_for','ruled_out','facts','writing','working_with_me')),
 items TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(items) AND json_type(items)='array'),
 version INTEGER NOT NULL DEFAULT 0, updated_at TEXT, updated_by TEXT
);
INSERT INTO preference_sections(section) VALUES ('looking_for'),('ruled_out'),('facts'),('working_with_me');
-- A new workspace starts with the one writing rule every document follows.
INSERT INTO preference_sections(section,items) VALUES ('writing',json_array(json_object('text',
 'Use only the supplied career evidence. Never invent qualifications, dates or metrics. '
 || 'Select relevant approved claims or write accurate new wording from detailed evidence. '
 || 'Respect the template and answer limits; make missing facts visible.','scope','all')));
-- Employer replies to sent applications (outcomes.py).
CREATE TABLE replies (
 id TEXT PRIMARY KEY, application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
 kind TEXT NOT NULL CHECK(kind IN ('rejection','interview','offer','other')),
 date TEXT NOT NULL CHECK(length(date)=10 AND date(date)=date),
 note TEXT NOT NULL DEFAULT '',
 created_by_kind TEXT, created_by_id TEXT, created_by_name TEXT, created_by_token_kind TEXT,
 updated_by_kind TEXT, updated_by_id TEXT, updated_by_name TEXT, updated_by_token_kind TEXT,
 version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX replies_application ON replies(application_id,date);
CREATE UNIQUE INDEX replies_once ON replies(application_id,kind,date) WHERE kind<>'other';
-- Local notes for a shipped skill (skill_notes.py): one immutable row per
-- version; the highest version is current. Appended when the skill is served.
CREATE TABLE skill_notes (
 skill TEXT NOT NULL CHECK(length(skill) BETWEEN 1 AND 100),
 version INTEGER NOT NULL CHECK(version>=1),
 text TEXT NOT NULL DEFAULT '' CHECK(length(text)<=2000),
 created_by_kind TEXT, created_by_id TEXT, created_by_name TEXT, created_by_token_kind TEXT,
 created_at TEXT NOT NULL,
 PRIMARY KEY(skill,version)
);
-- Ingest signals of each job (job_signals.py). Derived from the job and
-- rebuildable, except distinct_from (pairs the owner judged different vacancies).
CREATE TABLE job_signals (
 job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
 format INTEGER NOT NULL, content_version INTEGER NOT NULL,
 language TEXT, language_confidence REAL,
 required TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(required)),
 welcome TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(welcome)),
 duplicate_checked INTEGER NOT NULL DEFAULT 0 CHECK(duplicate_checked IN (0,1)),
 duplicate_of TEXT REFERENCES jobs(id) ON DELETE SET NULL, duplicate_confidence REAL,
 distinct_from TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(distinct_from)),
 computed_at TEXT NOT NULL
);
CREATE INDEX job_signals_duplicate ON job_signals(duplicate_of);
CREATE INDEX job_signals_language ON job_signals(language);
CREATE INDEX postings_unlisted ON postings(job_id) WHERE unlisted_at IS NOT NULL;
-- One pinned note per job and per application.
CREATE UNIQUE INDEX notes_pinned_application ON notes(application_id) WHERE pinned_at IS NOT NULL AND application_id IS NOT NULL;
CREATE UNIQUE INDEX notes_pinned_job ON notes(job_id) WHERE pinned_at IS NOT NULL AND application_id IS NULL;
CREATE INDEX notes_run ON notes(run_id);
-- Idempotency keys of creates (idempotency.py): the record's table, the key, the
-- SHA-256 of the request and the record it gave.
CREATE TABLE idempotency_keys (
 scope TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL,
 record_id TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(scope,key)
);
PRAGMA user_version=15;
