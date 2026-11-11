PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS settings (
 key TEXT PRIMARY KEY, data TEXT NOT NULL CHECK(json_valid(data)), version INTEGER NOT NULL DEFAULT 1,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS api_tokens (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL, last_used_at TEXT,
 kind TEXT NOT NULL DEFAULT 'owner' CHECK(kind IN ('owner','agent'))
);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, company TEXT NOT NULL, location TEXT NOT NULL DEFAULT '',
 url TEXT NOT NULL DEFAULT '', posting TEXT NOT NULL DEFAULT '', triage TEXT NOT NULL DEFAULT 'inbox'
 CHECK(triage IN ('inbox','saved','dismissed')), availability TEXT NOT NULL DEFAULT 'unknown',
 metadata TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(metadata)), overrides TEXT NOT NULL DEFAULT '{}',
 content_version INTEGER NOT NULL DEFAULT 1, version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_url ON jobs(url);
CREATE INDEX IF NOT EXISTS jobs_triage ON jobs(triage,created_at);
CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(title,company,posting,content='jobs',content_rowid='rowid');
CREATE TRIGGER IF NOT EXISTS jobs_ai AFTER INSERT ON jobs BEGIN
 INSERT INTO jobs_fts(rowid,title,company,posting) VALUES(new.rowid,new.title,new.company,new.posting); END;
CREATE TRIGGER IF NOT EXISTS jobs_ad AFTER DELETE ON jobs BEGIN
 INSERT INTO jobs_fts(jobs_fts,rowid,title,company,posting) VALUES('delete',old.rowid,old.title,old.company,old.posting); END;
CREATE TRIGGER IF NOT EXISTS jobs_au AFTER UPDATE OF title,company,posting ON jobs BEGIN
 INSERT INTO jobs_fts(jobs_fts,rowid,title,company,posting) VALUES('delete',old.rowid,old.title,old.company,old.posting);
 INSERT INTO jobs_fts(rowid,title,company,posting) VALUES(new.rowid,new.title,new.company,new.posting); END;
CREATE TABLE IF NOT EXISTS sources (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, config TEXT NOT NULL DEFAULT '{}',
 enabled INTEGER NOT NULL DEFAULT 0, schedule TEXT NOT NULL DEFAULT '{}', version INTEGER NOT NULL DEFAULT 1,
 last_run_at TEXT, last_scheduled_at TEXT, last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS postings (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 source_id TEXT REFERENCES sources(id) ON DELETE SET NULL, identity TEXT NOT NULL UNIQUE,
 url TEXT NOT NULL DEFAULT '', payload TEXT NOT NULL DEFAULT '{}', content_hash TEXT NOT NULL,
 first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS postings_job ON postings(job_id);
CREATE TABLE IF NOT EXISTS job_identities (
 identity TEXT NOT NULL, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 PRIMARY KEY(identity,job_id)
);
CREATE INDEX IF NOT EXISTS job_identities_job ON job_identities(job_id);
CREATE TABLE IF NOT EXISTS posting_details (
 identity TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 checked_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS posting_details_job ON posting_details(job_id);
CREATE TABLE IF NOT EXISTS applications (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','applied','interview','offer','closed')),
 outcome TEXT CHECK(outcome IS NULL OR outcome IN ('accepted','rejected','not_pursued')),
 note TEXT NOT NULL DEFAULT '', questions TEXT NOT NULL DEFAULT '[]', answers TEXT NOT NULL DEFAULT '{}',
 version INTEGER NOT NULL DEFAULT 1, idempotency_key TEXT UNIQUE, applied_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 priority INTEGER CHECK(priority IS NULL OR priority BETWEEN 1 AND 5),
 deadline TEXT CHECK(deadline IS NULL OR (length(deadline)=10 AND date(deadline)=deadline)),
 requirements TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(requirements) AND json_type(requirements)='array'),
 ready_at TEXT, ready_by_kind TEXT, ready_by_id TEXT, ready_by_name TEXT, ready_by_token_kind TEXT
);
-- An agent run: opened by an API token, closed with a stored report.
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, token_id TEXT NOT NULL, token_name TEXT NOT NULL,
 workflow TEXT NOT NULL, scope TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','finished','interrupted')),
 note TEXT NOT NULL DEFAULT '', report TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(report)),
 change_counts TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(change_counts)),
 superseded_by TEXT, idempotency_key TEXT UNIQUE, version INTEGER NOT NULL DEFAULT 1,
 started_at TEXT NOT NULL, last_activity_at TEXT NOT NULL, ended_at TEXT, updated_at TEXT NOT NULL,
 token_kind TEXT
);
-- One record per change. job_id/application_id keep the owning timeline (and its
-- deletion); subject_* names the changed record of any type; actor_* and run_id
-- say who changed it (a token with its kind, owner or agent). Rows written before
-- schema 8 have no actor.
CREATE TABLE IF NOT EXISTS events (
 id TEXT PRIMARY KEY, job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE,
 application_id TEXT REFERENCES applications(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
 subject_type TEXT, subject_id TEXT, actor_kind TEXT, actor_id TEXT, actor_name TEXT,
 actor_token_kind TEXT, run_id TEXT REFERENCES runs(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS events_app ON events(application_id,created_at);
CREATE TABLE IF NOT EXISTS notes (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 application_id TEXT REFERENCES applications(id) ON DELETE CASCADE, body TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 author_kind TEXT, author_id TEXT, author_name TEXT, author_token_kind TEXT
);
CREATE TABLE IF NOT EXISTS knowledge (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, organization TEXT NOT NULL DEFAULT '',
 dates TEXT CHECK(dates IS NULL OR json_valid(dates)), skills TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(skills)),
 position INTEGER NOT NULL DEFAULT 0 CHECK(position>=0), narrative TEXT NOT NULL DEFAULT '',
 metadata TEXT NOT NULL DEFAULT '{}', version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claims (
 id TEXT PRIMARY KEY, knowledge_id TEXT NOT NULL REFERENCES knowledge(id) ON DELETE CASCADE,
 text TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0, position INTEGER NOT NULL DEFAULT 0 CHECK(position>=0), metadata TEXT NOT NULL DEFAULT '{}',
 version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS templates (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('resume','cover_letter')),
 tex TEXT NOT NULL DEFAULT '', guidance TEXT NOT NULL DEFAULT '', rules TEXT NOT NULL DEFAULT '{}',
 is_default INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS templates_default ON templates(kind) WHERE is_default=1;
CREATE TABLE IF NOT EXISTS contexts (
 id TEXT PRIMARY KEY, application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
 payload TEXT NOT NULL, signature TEXT NOT NULL, idempotency_key TEXT UNIQUE, created_at TEXT NOT NULL
);
-- Derived from immutable contexts: the input versions each context froze. Rebuildable.
CREATE TABLE IF NOT EXISTS context_inputs (
 context_id TEXT PRIMARY KEY REFERENCES contexts(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL, profile_version INTEGER, instructions_version INTEGER,
 templates TEXT NOT NULL DEFAULT '[]', knowledge TEXT NOT NULL DEFAULT '[]', claims TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY, application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
 context_id TEXT REFERENCES contexts(id) ON DELETE CASCADE, kind TEXT NOT NULL,
 title TEXT NOT NULL DEFAULT '', content TEXT NOT NULL DEFAULT '{}',
 previous_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
 review_state TEXT NOT NULL DEFAULT 'draft', version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blobs (
 sha256 TEXT PRIMARY KEY, content BLOB NOT NULL, size INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
 id TEXT PRIMARY KEY, sha256 TEXT NOT NULL REFERENCES blobs(sha256), name TEXT NOT NULL,
 media_type TEXT NOT NULL DEFAULT 'application/octet-stream', size INTEGER NOT NULL,
 knowledge_id TEXT REFERENCES knowledge(id) ON DELETE CASCADE,
 template_id TEXT REFERENCES templates(id) ON DELETE CASCADE,
 context_id TEXT REFERENCES contexts(id) ON DELETE CASCADE,
 document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
 job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE, created_at TEXT NOT NULL,
 CHECK((knowledge_id IS NOT NULL)+(template_id IS NOT NULL)+(context_id IS NOT NULL)+
       (document_id IS NOT NULL)+(job_id IS NOT NULL)=1)
);
CREATE TABLE IF NOT EXISTS transfer_grants (
 token_hash TEXT PRIMARY KEY, payload TEXT NOT NULL, method TEXT NOT NULL,
 expires_at TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS collection_runs (
 id TEXT PRIMARY KEY, source_id TEXT REFERENCES sources(id) ON DELETE SET NULL,
 source_name TEXT NOT NULL, source_version INTEGER NOT NULL,
 source_snapshot TEXT NOT NULL CHECK(json_valid(source_snapshot)),
 overrides TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(overrides)), planned_at TEXT,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS collection_runs_source ON collection_runs(source_id,created_at);
CREATE TABLE IF NOT EXISTS tasks (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, source_id TEXT REFERENCES sources(id) ON DELETE SET NULL,
 run_id TEXT REFERENCES collection_runs(id) ON DELETE CASCADE,
 job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE, state TEXT NOT NULL DEFAULT 'queued',
 payload TEXT NOT NULL DEFAULT '{}', result TEXT NOT NULL DEFAULT '{}', attempts INTEGER NOT NULL DEFAULT 0,
 dedupe_key TEXT UNIQUE, next_run_at TEXT NOT NULL, lease_until TEXT, lease_owner TEXT, error TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS tasks_run ON tasks(run_id);
CREATE INDEX IF NOT EXISTS tasks_due ON tasks(state,next_run_at);
CREATE TABLE IF NOT EXISTS providers (
 id TEXT PRIMARY KEY, policy TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(policy)),
 runtime TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(runtime)), version INTEGER NOT NULL DEFAULT 1,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS applications_job ON applications(job_id,created_at DESC,id DESC);
CREATE UNIQUE INDEX IF NOT EXISTS applications_active_job ON applications(job_id) WHERE status<>'closed';
CREATE INDEX IF NOT EXISTS applications_status ON applications(status,updated_at);
CREATE INDEX IF NOT EXISTS applications_deadline ON applications(deadline);
CREATE INDEX IF NOT EXISTS applications_ready ON applications(ready_at) WHERE ready_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS documents_app ON documents(application_id,created_at);
CREATE INDEX IF NOT EXISTS documents_context ON documents(context_id);
CREATE INDEX IF NOT EXISTS contexts_app ON contexts(application_id,created_at);
CREATE INDEX IF NOT EXISTS files_document ON files(document_id);
CREATE INDEX IF NOT EXISTS files_context ON files(context_id);
CREATE INDEX IF NOT EXISTS files_template ON files(template_id);
CREATE INDEX IF NOT EXISTS files_knowledge ON files(knowledge_id);
CREATE INDEX IF NOT EXISTS claims_knowledge ON claims(knowledge_id);
CREATE INDEX IF NOT EXISTS documents_previous ON documents(previous_id);
CREATE INDEX IF NOT EXISTS events_job ON events(job_id);
CREATE INDEX IF NOT EXISTS events_created ON events(created_at);
CREATE INDEX IF NOT EXISTS notes_job ON notes(job_id,created_at);
CREATE INDEX IF NOT EXISTS notes_app ON notes(application_id);
CREATE INDEX IF NOT EXISTS files_job ON files(job_id);
CREATE INDEX IF NOT EXISTS files_blob ON files(sha256);
CREATE INDEX IF NOT EXISTS tasks_job ON tasks(job_id);
CREATE INDEX IF NOT EXISTS tasks_source ON tasks(source_id);
CREATE INDEX IF NOT EXISTS postings_source ON postings(source_id);
-- A question for the owner. The subject reference becomes NULL when its record is
-- deleted; subject_type and subject_label keep the question readable.
CREATE TABLE IF NOT EXISTS questions (
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
 idempotency_key TEXT UNIQUE, version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK((job_id IS NOT NULL)+(application_id IS NOT NULL)+(knowledge_id IS NOT NULL)<=1)
);
CREATE UNIQUE INDEX IF NOT EXISTS runs_open_token ON runs(token_id) WHERE status='open';
CREATE INDEX IF NOT EXISTS runs_token ON runs(token_id,started_at);
CREATE INDEX IF NOT EXISTS runs_status ON runs(status,started_at);
CREATE INDEX IF NOT EXISTS runs_started ON runs(started_at);
CREATE INDEX IF NOT EXISTS events_run ON events(run_id,created_at);
CREATE INDEX IF NOT EXISTS events_subject ON events(subject_type,subject_id,created_at);
CREATE INDEX IF NOT EXISTS questions_state ON questions(state,created_at);
CREATE INDEX IF NOT EXISTS questions_resolved ON questions(state,resolved_at);
CREATE INDEX IF NOT EXISTS questions_job ON questions(job_id);
CREATE INDEX IF NOT EXISTS questions_application ON questions(application_id);
CREATE INDEX IF NOT EXISTS questions_knowledge ON questions(knowledge_id);
CREATE INDEX IF NOT EXISTS questions_run ON questions(run_id);
PRAGMA user_version=8;
