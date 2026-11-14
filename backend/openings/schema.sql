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
 kind TEXT NOT NULL DEFAULT 'owner' CHECK(kind IN ('owner','agent')),
 -- The token's previous workspace_context read: owner corrections after it are feedback.
 context_read_at TEXT
);
CREATE TABLE jobs (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, company TEXT NOT NULL, location TEXT NOT NULL DEFAULT '',
 url TEXT NOT NULL DEFAULT '', posting TEXT NOT NULL DEFAULT '', triage TEXT NOT NULL DEFAULT 'new'
 CHECK(triage IN ('new','shortlisted','dismissed')),
 metadata TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(metadata)), overrides TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(overrides)),
 content_version INTEGER NOT NULL DEFAULT 1, version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 -- The current dismissal: when, by whom (an actor label, see events) and why.
 -- Cleared on restore.
 dismissed_at TEXT, dismissed_by TEXT, dismissed_reason TEXT NOT NULL DEFAULT ''
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
-- One record per change. job_id/application_id keep the owning timeline (and its
-- deletion); subject_* names the changed record of any type. actor is the actor
-- label of who changed it: owner (the dashboard session or an owner token),
-- agent:<token name> (an agent token) or system (collection, worker, upgrade);
-- NULL before 0.17. batch_id groups the changes of one REST request or MCP tool
-- call (b_<ULID>), or of one former agent run (run:<id>).
CREATE TABLE events (
 id TEXT PRIMARY KEY, job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE,
 application_id TEXT REFERENCES applications(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(payload)), created_at TEXT NOT NULL,
 subject_type TEXT, subject_id TEXT, actor TEXT, batch_id TEXT
);
CREATE INDEX events_app ON events(application_id,created_at);
-- A note on a job, or on one application when application_id is set (its scope).
-- author is the actor label of who wrote it; pinned_at marks the one pinned note
-- of its scope.
CREATE TABLE notes (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 application_id TEXT REFERENCES applications(id) ON DELETE CASCADE, body TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 author TEXT, pinned_at TEXT
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
 -- ★ "Always include in my CV": in the CV unless the job gives a reason to leave it out.
 always_include INTEGER NOT NULL DEFAULT 0 CHECK(always_include IN (0,1))
);
CREATE TABLE templates (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('cv','letter')),
 tex TEXT NOT NULL DEFAULT '', guidance TEXT NOT NULL DEFAULT '', rules TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(rules)),
 is_default INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX templates_default ON templates(kind) WHERE is_default=1;
-- A document revision. A CV or letter (cv, letter) is its PDF and optional .tex
-- source (files): it is complete once its PDF is stored. content stays '{}'; text is
-- the readable text, from the source (text_from 'tex', documents/text.py) or else
-- from the PDF ('pdf', documents/pdf.py), NULL when none could be read.
-- Form answers and other kinds keep structured content. claim_ids and
-- knowledge_ids are the evidence it cites.
CREATE TABLE documents (
 id TEXT PRIMARY KEY, application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
 kind TEXT NOT NULL,
 title TEXT NOT NULL DEFAULT '', content TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(content)),
 previous_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
 version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
 text TEXT, text_from TEXT CHECK(text_from IS NULL OR text_from IN ('tex','pdf')),
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
 document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
 job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE, created_at TEXT NOT NULL,
 -- The SHA-256 of the source a revision's PDF was built from; NULL for every other
 -- file, for a PDF-only revision and for PDFs uploaded before 0.22.
 source_sha256 TEXT,
 CHECK((knowledge_id IS NOT NULL)+(template_id IS NOT NULL)+(document_id IS NOT NULL)+
       (job_id IS NOT NULL)=1)
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
CREATE INDEX files_document ON files(document_id);
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
-- Also counts the jobs of each source (sources_list counts, #211).
CREATE INDEX postings_source ON postings(source_id,job_id);
CREATE INDEX events_batch ON events(batch_id,created_at);
CREATE INDEX events_subject ON events(subject_type,subject_id,created_at);
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
 created_by TEXT, updated_by TEXT,
 version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX replies_application ON replies(application_id,date);
CREATE UNIQUE INDEX replies_once ON replies(application_id,kind,date) WHERE kind<>'other';
-- Ingest signals of each job (job_signals.py). Derived from the job and
-- rebuildable, except distinct_from (pairs the owner judged different vacancies).
CREATE TABLE job_signals (
 job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
 format INTEGER NOT NULL, content_version INTEGER NOT NULL,
 language TEXT, language_confidence REAL,
 required TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(required)),
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
-- Idempotency keys of creates (idempotency.py): the record's table, the key, the
-- SHA-256 of the request and the record it gave.
CREATE TABLE idempotency_keys (
 scope TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL,
 record_id TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(scope,key)
);
PRAGMA user_version=15;
