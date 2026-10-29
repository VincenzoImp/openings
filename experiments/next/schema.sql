PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS profile (
    id TEXT PRIMARY KEY,
    basics TEXT NOT NULL CHECK(json_valid(basics)),
    version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profile(id),
    kind TEXT NOT NULL CHECK(kind IN ('experience','project','course','fact')),
    title TEXT NOT NULL,
    narrative TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS claim (
    id TEXT PRIMARY KEY,
    evidence_id TEXT NOT NULL REFERENCES evidence(id),
    text TEXT NOT NULL,
    approved INTEGER NOT NULL DEFAULT 0 CHECK(approved IN (0,1)),
    version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS template (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('resume','cover_letter')),
    tex TEXT NOT NULL,
    rules TEXT NOT NULL CHECK(json_valid(rules)),
    prompt_append TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS job (
    id TEXT PRIMARY KEY,
    source_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    posting TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS application (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES job(id),
    profile_id TEXT NOT NULL REFERENCES profile(id),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK(status IN ('draft','applied','screening','interview','offer','accepted','rejected','withdrawn')),
    version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS run (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES application(id),
    idempotency_key TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','review','failed')),
    snapshot TEXT NOT NULL CHECK(json_valid(snapshot)),
    snapshot_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blob (
    sha256 TEXT PRIMARY KEY,
    media_type TEXT NOT NULL,
    content BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS artifact (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES run(id),
    content TEXT NOT NULL CHECK(json_valid(content)),
    content_hash TEXT NOT NULL,
    blob_sha TEXT REFERENCES blob(sha256),
    review_state TEXT NOT NULL DEFAULT 'needs_review' CHECK(review_state IN ('needs_review','approved')),
    UNIQUE(run_id, content_hash)
);
PRAGMA user_version = 1;
