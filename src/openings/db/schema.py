"""The SQLite schema. Created by the running version; there is no migration."""

SCHEMA = """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        identity TEXT NOT NULL,
        title TEXT NOT NULL,
        company TEXT NOT NULL,
        location TEXT NOT NULL,
        source TEXT NOT NULL,
        external_id TEXT,
        job_url TEXT,
        description TEXT,
        date_posted DATE,
        job_type TEXT,
        is_remote BOOLEAN,
        job_level TEXT,
        min_amount REAL,
        max_amount REAL,
        currency TEXT,
        salary_interval TEXT,
        company_url TEXT,
        raw_json TEXT,
        first_seen DATE NOT NULL,
        last_seen DATE NOT NULL,
        relevance_score INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'new',
        status_changed_at TIMESTAMP NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_jobs_identity ON jobs(identity);
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
    CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(relevance_score);
    CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen);
    CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);

    CREATE TABLE IF NOT EXISTS postings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
        key TEXT NOT NULL UNIQUE,
        source TEXT NOT NULL,
        external_id TEXT,
        url TEXT,
        first_seen DATE NOT NULL,
        last_seen DATE NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_postings_job ON postings(job_id);

    CREATE TABLE IF NOT EXISTS job_labels (
        job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
        label TEXT NOT NULL,
        PRIMARY KEY (job_id, label)
    );
    CREATE INDEX IF NOT EXISTS idx_job_labels_label ON job_labels(label);

    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        title TEXT,
        body TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_notes_job ON notes(job_id);

    CREATE TABLE IF NOT EXISTS attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        filename TEXT NOT NULL,
        stored_name TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        note TEXT,
        created_at TIMESTAMP NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_attachments_job ON attachments(job_id);
    CREATE INDEX IF NOT EXISTS idx_attachments_kind ON attachments(kind);

    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        summary TEXT NOT NULL,
        data_json TEXT,
        created_at TIMESTAMP NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_events_job ON events(job_id, created_at);

    CREATE TABLE IF NOT EXISTS embeddings (
        job_id TEXT PRIMARY KEY REFERENCES jobs(job_id) ON DELETE CASCADE,
        model TEXT NOT NULL,
        vector BLOB NOT NULL,
        updated_at TIMESTAMP NOT NULL
    );

    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TIMESTAMP NOT NULL,
        finished_at TIMESTAMP,
        total_found INTEGER NOT NULL DEFAULT 0,
        unique_found INTEGER NOT NULL DEFAULT 0,
        saved INTEGER NOT NULL DEFAULT 0,
        new_jobs INTEGER NOT NULL DEFAULT 0,
        notified INTEGER NOT NULL DEFAULT 0,
        success BOOLEAN NOT NULL DEFAULT 1,
        sources_json TEXT NOT NULL DEFAULT '[]',
        errors_json TEXT NOT NULL DEFAULT '[]'
    );
"""
