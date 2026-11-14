// Generated from the backend's OpenAPI document by `npm run api:gen`.
// Do not edit: change the backend models and run `npm run api:gen` again.

export interface paths {
  "/api/v1/applications": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Search application summaries.
     * @description Pages with stage counts; each row has ready, missing and last_reply. Filter by job_id, text, stage (ready: Shortlisted and Ready), outcome, company, needs and applied dates. no_reply gives the period and the overdue count.
     */
    get: operations["applications_list"];
    put?: never;
    /**
     * Start an application.
     * @description Stage Shortlisted; shortlists its job. Optional required_documents (default cv and letter), priority, deadline, questions and requirements. Never sends an application.
     */
    post: operations["applications_create"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/applications/{application_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read an application in full.
     * @description Its job, requirements, questions and answers, required_documents, ready and missing, replies and pinned_note (the owner's guidance).
     */
    get: operations["applications_get"];
    put?: never;
    post?: never;
    /**
     * Delete an application.
     * @description Deletes it with its documents and history; the job and other applications stay.
     */
    delete: operations["applications_delete"];
    options?: never;
    head?: never;
    /**
     * Update an application.
     * @description Stage, reply, outcome, priority, deadline, documents, requirements, answers. Mark applied (status=applied) only when the owner says it was sent. A reply moves the stage. Close as no_response only when the owner asks.
     */
    patch: operations["applications_update"];
    trace?: never;
  };
  "/api/v1/applications/{application_id}/events": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read an application's recorded changes.
     * @description timeline_get lists them with its notes and its job's entries.
     */
    get: operations["applications_history"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/applications/{application_id}/timeline": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read the timeline of a job or an application.
     * @description Give job_id or application_id. Notes and recorded changes, pinned notes first, then newest first, each with kind, scope, actor and batch_id. Filter by kinds, who, scope and dates; counts per kind.
     */
    get: operations["timeline_get_1"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/applications/bulk": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Close, reopen or delete selected applications.
     * @description Up to 200 ids with versions, one result each. close takes an outcome (no_response only for a sent application, when the owner asks); reopen a stage. Record replies with applications_update.
     */
    post: operations["applications_bulk"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/login": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Login
     * @description Sign the browser in with the owner password.
     */
    post: operations["login_api_v1_auth_login_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/logout": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Logout
     * @description Sign out every browser session; API and MCP tokens stay valid.
     */
    post: operations["logout_api_v1_auth_logout_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/password": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Change the owner password.
     * @description Signs out every browser session; API and MCP tokens stay valid.
     *
     *     Owner only: an agent token is refused with 403 forbidden; not an MCP tool.
     */
    post: operations["owner_password_update"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/session": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Session
     * @description Read the browser session state and its CSRF token.
     */
    get: operations["session_api_v1_auth_session_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/setup": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Setup
     * @description Set the owner password once and sign the browser in.
     */
    post: operations["setup_api_v1_auth_setup_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/backup": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Backup
     * @description Download a consistent SQLite backup with file bytes.
     *
     *     With an agent token or its grant, the owner password hash, session secret and
     *     tokens are left out.
     */
    get: operations["backup_api_v1_backup_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/backup/grant": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Reserve a backup download.
     * @description A two-minute GET grant for a consistent SQLite backup with file bytes. With an agent token the backup omits the password hash, session secret and tokens; it still restores.
     */
    post: operations["workspace_backup"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/backup/restore": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Restore
     * @description Replace the workspace data with a SQLite backup (owner only).
     *
     *     Send the raw file as application/vnd.sqlite3. Installation authentication stays.
     *
     *     Owner only: an agent token is refused with 403 forbidden; not an MCP tool.
     */
    post: operations["restore_api_v1_backup_restore_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/backups": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List kept backups.
     * @description Scheduled backups and pre-upgrade copies, with the schedule and its last result.
     *
     *     Owner only: an agent token is refused with 403 forbidden; not an MCP tool.
     */
    get: operations["backups_list"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/backups/{name}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Backup File
     * @description Download a kept backup or pre-upgrade copy (owner only).
     *
     *     Owner only: an agent token is refused with 403 forbidden; not an MCP tool.
     */
    get: operations["backup_file_api_v1_backups__name__get"];
    put?: never;
    post?: never;
    /**
     * Delete a pre-upgrade copy.
     * @description Scheduled backups rotate by themselves.
     *
     *     Owner only: an agent token is refused with 403 forbidden; not an MCP tool.
     */
    delete: operations["backups_delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/capabilities": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Capabilities
     * @description Read the version, schema, this token's kind and each operation's route and access.
     */
    get: operations["capabilities_api_v1_capabilities_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/career/claims": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Search highlights.
     * @description By entry (knowledge_id), approval or text (q). summary=true (default) bounds previews and omits metadata; always_include is always returned.
     */
    get: operations["claims_list"];
    put?: never;
    /**
     * Add a highlight.
     * @description Reusable wording tied to a career entry; not approved by default. always_include puts it in every CV unless the job gives a reason to leave it out.
     */
    post: operations["claims_create"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/career/claims/{claim_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read a highlight and its entry id.
     * @description Read a highlight and its entry id.
     */
    get: operations["claims_get"];
    put?: never;
    post?: never;
    /**
     * Delete a highlight.
     * @description Permanently; document revisions keep the ids they cite.
     */
    delete: operations["claims_delete"];
    options?: never;
    head?: never;
    /**
     * Edit or approve a highlight.
     * @description With its version. Writing documents never approves new facts.
     */
    patch: operations["claims_update"];
    trace?: never;
  };
  "/api/v1/career/import": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Import previewed career entries.
     * @description Appends the entries and, with the profile's version, applies the profile fields.
     */
    post: operations["career_import"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/career/import/preview": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Preview a career import.
     * @description Parses JSON or plain text into entries and profile fields without storing anything.
     */
    post: operations["career_preview_import"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/career/knowledge": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Search career entries.
     * @description By q (title, organization, narrative) and kind. summary=true (default) returns previews and counts, summary=false full records; knowledge_get reads one.
     */
    get: operations["knowledge_list"];
    put?: never;
    /**
     * Add a career entry.
     * @description Facts come from the owner, never from a job posting.
     */
    post: operations["knowledge_create"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/career/knowledge/{knowledge_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read a career entry with its full narrative and metadata.
     * @description Read a career entry with its full narrative and metadata.
     */
    get: operations["knowledge_get"];
    put?: never;
    post?: never;
    /**
     * Delete a career entry.
     * @description Permanently, with its highlights and files; document revisions are unchanged.
     */
    delete: operations["knowledge_delete"];
    options?: never;
    head?: never;
    /**
     * Edit a career entry.
     * @description With its version; dates=null clears the dates. Document revisions keep the ids they cite.
     */
    patch: operations["knowledge_update"];
    trace?: never;
  };
  "/api/v1/career/profile": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read the profile and its version.
     * @description Read the profile and its version.
     */
    get: operations["profile_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Edit the profile.
     * @description Name, contact, headline, summary, links and metadata, with the profile's version.
     */
    patch: operations["profile_update"];
    trace?: never;
  };
  "/api/v1/collection": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read the collection switch, counts and next queued run.
     * @description Read the collection switch, counts and next queued run.
     */
    get: operations["collection_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Pause or resume scheduled collection.
     * @description With its version; running a source by hand stays available.
     */
    patch: operations["collection_update"];
    trace?: never;
  };
  "/api/v1/collection/runs": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List collection runs.
     * @description With provider counts and timing, by source_id or state. summary=false adds source snapshots and full task records.
     */
    get: operations["collection_runs_list"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/collection/runs/{run_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read a collection run.
     * @description Its frozen settings, progress and provider tasks.
     */
    get: operations["collection_runs_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/collection/runs/{run_id}/cancel": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Stop a collection run.
     * @description Jobs already archived stay.
     */
    post: operations["collection_runs_cancel"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/documents": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List document revisions.
     * @description By application and kind (cv, letter, answers, other), each with complete; q searches titles, notes and text. summary=false adds text, content and files.
     */
    get: operations["documents_list"];
    put?: never;
    /**
     * Create a document revision.
     * @description A CV or letter gives pdf (name, size) and optionally its TeX source; PUT the bytes to the returned uploads grants, source first. Complete once its PDF is stored. Never sends.
     */
    post: operations["documents_create"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/documents/{document_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read a document revision.
     * @description complete, readable text and text_from (tex or pdf), cited evidence, note and files; for other kinds the structured content.
     */
    get: operations["documents_get"];
    put?: never;
    post?: never;
    /**
     * Delete a document revision.
     * @description Permanently, with its files and version; other revisions stay.
     */
    delete: operations["documents_delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/documents/{document_id}/comparison": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Compare two revisions line by line.
     * @description With other_id, or by default the revision it replaces; CV and letter compare their text.
     */
    get: operations["documents_compare"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/events": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List recorded changes.
     * @description Newest first, each with its actor label, batch_id and subject. Filter by actor, batch_id, dates, job, application, subject or kind; system changes only with actor=system or include_system.
     */
    get: operations["events_list"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/examples": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Examples
     * @description List the shipped example files.
     */
    get: operations["examples_api_v1_examples_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/examples/{name}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Example File
     * @description Download a shipped example file.
     */
    get: operations["example_file_api_v1_examples__name__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/export": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Export
     * @description Download the workspace records as JSON, without file bytes or credentials.
     */
    get: operations["export_api_v1_export_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/export/grant": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Reserve a records export.
     * @description A two-minute GET grant for redacted JSON records, without file bytes or installation authentication; a backup is the full snapshot.
     */
    post: operations["workspace_export"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/files": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List file metadata.
     * @description By owner, name, media type or an application's revisions. Bytes go through transfers.
     */
    get: operations["files_list"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/files/{file_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read file metadata and its content URL.
     * @description Read file metadata and its content URL.
     */
    get: operations["files_get"];
    put?: never;
    post?: never;
    /**
     * Delete a file.
     * @description A career entry, template or job file, with version 1. Revision files are immutable: delete the revision.
     */
    delete: operations["files_delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/files/{file_id}/content": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * File Content
     * @description Read a file's bytes; inline=false downloads it.
     */
    get: operations["file_content_api_v1_files__file_id__content_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/files/{file_id}/download": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Reserve a file download.
     * @description A short-lived GET grant for one file; resolve its url against this workspace.
     */
    post: operations["files_reserve_download"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/files/uploads": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Reserve a file upload.
     * @description A short-lived PUT grant for one owner, name and size: send the raw bytes to its url with its headers. sha256 is verified when given.
     */
    post: operations["files_reserve_upload"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/jobs": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Search job summaries.
     * @description Compact pages filtered by triage, text, company, location, source, dates, signals (language, required languages, likely duplicate, no longer listed), who dismissed them or batch_id. include_counts and include_facets add totals; jobs_get has the text.
     */
    get: operations["jobs_list"];
    put?: never;
    /**
     * Add a job from a URL, pasted text or fields.
     * @description A URL is read through the provider gate. A known identity adds to its job's history; a new job gets its signals. A retry with the same idempotency_key returns the same job.
     */
    post: operations["jobs_create"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/jobs/{job_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read a job in full.
     * @description Posting text, metadata, version, observations (unlisted_at when a board stopped listing one), signals and dismissal.
     */
    get: operations["jobs_get"];
    put?: never;
    post?: never;
    /**
     * Forget a job permanently.
     * @description Deletes the job, its applications and files; acquiring it again later makes a new job.
     */
    delete: operations["jobs_delete"];
    options?: never;
    head?: never;
    /**
     * Correct a job's fields.
     * @description With the version jobs_get returned; returns the compact summary.
     */
    patch: operations["jobs_update"];
    trace?: never;
  };
  "/api/v1/jobs/{job_id}/distinct": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Mark a likely duplicate as a different vacancy.
     * @description The duplicate flag against other_id is cleared for good. Merge verified duplicates with jobs_merge instead.
     */
    post: operations["jobs_distinct"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/jobs/{job_id}/merge": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Merge verified duplicate jobs.
     * @description Merges the job into target_id, keeping postings, applications and notes.
     */
    post: operations["jobs_merge"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/jobs/{job_id}/notes": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List the notes of a job and its applications.
     * @description Pinned first, each with its scope and author. timeline_get lists them with the changes.
     */
    get: operations["notes_list"];
    put?: never;
    /**
     * Add a note to a job or one of its applications.
     * @description application_id puts it on the application. pinned=true lists it first and unpins the previous one; an application's pinned note is the owner's guidance for its documents.
     */
    post: operations["notes_create"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/jobs/{job_id}/timeline": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read the timeline of a job or an application.
     * @description Give job_id or application_id. Notes and recorded changes, pinned notes first, then newest first, each with kind, scope, actor and batch_id. Filter by kinds, who, scope and dates; counts per kind.
     */
    get: operations["timeline_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/jobs/{job_id}/triage": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Shortlist, dismiss or return a job to review.
     * @description shortlisted starts the job's application. Back to new or dismissed removes it only while it is empty (else 409 application_has_work). Give a short reason when dismissing; a dismissal can be restored.
     */
    post: operations["jobs_triage"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/jobs/bulk": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Shortlist, dismiss, restore or forget selected jobs.
     * @description Up to 200 job ids with versions, one result each. shortlisted starts each application; new or dismissed undoes a shortlist whose application is empty; reason goes with dismissed; forget is permanent.
     */
    post: operations["jobs_bulk"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/jobs/duplicates": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List candidate duplicate job groups.
     * @description Most confident first, each with a confidence in [0,1], a tier and the signals that matched or conflicted. min_confidence defaults to 0.5 (0 lists all). Verify before jobs_merge; never merges.
     */
    get: operations["jobs_duplicates"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/jobs/resolve": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Look up archived jobs by URL or source key.
     * @description Archived jobs matching a url or source_key, with triage and every application. Never ingests or fetches.
     */
    get: operations["jobs_resolve"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/notes/{note_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read a note and its version.
     * @description Read a note and its version.
     */
    get: operations["notes_get"];
    put?: never;
    post?: never;
    /**
     * Delete a note.
     * @description With its version; the history records the deletion.
     */
    delete: operations["notes_delete"];
    options?: never;
    head?: never;
    /**
     * Edit a note.
     * @description Replaces its body, with its version.
     */
    patch: operations["notes_update"];
    trace?: never;
  };
  "/api/v1/notes/{note_id}/pin": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Pin or unpin a note.
     * @description With its version. One pinned note per job and per application: pinning unpins the other.
     */
    post: operations["notes_pin"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/preferences": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read the owner's Preferences and settings.
     * @description In the owner's words: looking_for, ruled_out, facts, writing (scope all, cv or letter) and working_with_me, each versioned; and no_reply_days and spoken_languages. Nothing acts automatically.
     */
    get: operations["preferences_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/preferences/{section}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /**
     * Replace a Preferences section.
     * @description The whole list of items with the section's version (on a conflict read again and merge). Keep the owner's wording; change only what the owner asked or confirmed.
     */
    put: operations["preferences_update"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/providers": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List providers.
     * @description Supported providers, their editable HTTP safeguards and the shared window and cooldown.
     */
    get: operations["providers_list"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/providers/{provider_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Edit a provider's HTTP policy.
     * @description With its version. Runtime and cooldown are read-only and shared by all runs.
     */
    patch: operations["providers_update"];
    trace?: never;
  };
  "/api/v1/settings": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change the no-reply period or the spoken languages.
     * @description no_reply_days (1-365) or spoken_languages (ISO 639-1 codes, used by hide_unspoken_required), with the settings' version.
     */
    patch: operations["settings_update"];
    trace?: never;
  };
  "/api/v1/skills": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List the shipped agent skills.
     * @description Workflow skills for agents using Openings, with what the owner can ask and their reference files. Read one with skills_get.
     */
    get: operations["skills_list"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/skills/{name}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read a skill or one of its reference files.
     * @description SKILL.md or a listed reference file (path), as Markdown; relative links resolve against the skill's directory. The owner's instructions are in Preferences.
     */
    get: operations["skills_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/skills/{name}/files/{path}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Skill File
     * @description Read a skill's reference file by path, as skills_get with path.
     */
    get: operations["skill_file_api_v1_skills__name__files__path__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/sources": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List sources.
     * @description Saved searches and company feeds with schedules, outcomes and counts of jobs found, shortlisted, applied and replied. summary=false adds run diagnostics.
     */
    get: operations["sources_list"];
    put?: never;
    /**
     * Save a source.
     * @description One saved search (query and location) or company feed; paused by default.
     */
    post: operations["sources_create"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/sources/{source_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read a source's configuration and version.
     * @description Read a source's configuration and version.
     */
    get: operations["sources_get"];
    put?: never;
    post?: never;
    /**
     * Delete a source.
     * @description Archived jobs and collection history stay.
     */
    delete: operations["sources_delete"];
    options?: never;
    head?: never;
    /**
     * Edit or pause a source.
     * @description With its version.
     */
    patch: operations["sources_update"];
    trace?: never;
  };
  "/api/v1/sources/{source_id}/run": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Run a source now.
     * @description With its version and optional one-time overrides; the provider gate applies.
     */
    post: operations["sources_run"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/sources/bulk": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Enable, pause, run, configure or delete selected sources.
     * @description Ids with versions, one result or error each.
     */
    post: operations["sources_bulk"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/sources/preview": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Preview a source without storing jobs.
     * @description Requests go through the provider gate (spacing and cooldowns).
     */
    post: operations["sources_preview"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/sources/schemas": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Describe source fields.
     * @description Supported fields and defaults, schedule variants and run options of each kind.
     */
    get: operations["sources_schemas"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/stats": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read how employers answered.
     * @description Applications sent in a period (90d, 12m, all): replies and interviews with rates, median days to the first reply, the funnel, and replies by source when there is enough data.
     */
    get: operations["stats_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/tasks": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List collection tasks.
     * @description By state, kind, source or job, with labels and diagnostics.
     */
    get: operations["tasks_list"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/tasks/{task_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read a task.
     * @description Inputs, result, HTTP diagnostics, lease and next run time.
     */
    get: operations["tasks_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/tasks/{task_id}/cancel": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Cancel a queued or running task.
     * @description Jobs and documents already stored stay.
     */
    post: operations["tasks_cancel"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/tasks/{task_id}/retry": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Retry a failed or cancelled task.
     * @description With its frozen inputs and saved progress.
     */
    post: operations["tasks_retry"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/templates": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List templates.
     * @description By kind or q. summary=true (default) omits TeX, guidance and rules. Read the template before editing or compiling externally.
     */
    get: operations["templates_list"];
    put?: never;
    /**
     * Add a template.
     * @description Source, guidance and rules; the first template of a kind becomes its default.
     */
    post: operations["templates_create"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/templates/{template_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read a template.
     * @description Its source, guidance and rules (limits and settings); fetch its files separately.
     */
    get: operations["templates_get"];
    put?: never;
    post?: never;
    /**
     * Delete a template.
     * @description With its files; document revisions are unchanged.
     */
    delete: operations["templates_delete"];
    options?: never;
    head?: never;
    /**
     * Edit a template.
     * @description Source, default, guidance or rules, with its version.
     */
    patch: operations["templates_update"];
    trace?: never;
  };
  "/api/v1/tokens": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List API tokens.
     * @description Names, kinds and use; secrets are never returned.
     *
     *     Owner only: an agent token is refused with 403 forbidden; not an MCP tool.
     */
    get: operations["tokens_list"];
    put?: never;
    /**
     * Create an API token.
     * @description A named agent (scoped, the default) or owner token. Its secret is returned only once.
     *
     *     Owner only: an agent token is refused with 403 forbidden; not an MCP tool.
     */
    post: operations["tokens_create"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/tokens/{token_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /**
     * Revoke an API token.
     * @description Including the token making the request.
     *
     *     Owner only: an agent token is refused with 403 forbidden; not an MCP tool.
     */
    delete: operations["tokens_revoke"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/transfers": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Download
     * @description Download raw file bytes with a grant (X-Transfer-Token).
     */
    get: operations["download_api_v1_transfers_get"];
    /**
     * Upload
     * @description Upload raw file bytes with a grant.
     *
     *     The second step of files_reserve_upload or of a revision's uploads: PUT the exact
     *     bytes to the grant's url with its headers (X-Transfer-Token). Returns the file.
     */
    put: operations["upload_api_v1_transfers_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/workspace": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read the workspace identity.
     * @description The version and schema_version, who this token is (actor: owner or agent:<token name>, the label its changes carry), storage (size, free space, restore limit, retention) and the workflow. File bytes use REST transfer grants.
     */
    get: operations["workspace_info"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/health": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Health
     * @description Report liveness, the last backup and the worker heartbeat.
     */
    get: operations["health_health_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
}
export type webhooks = Record<string, never>;
export interface components {
  schemas: {
    /**
     * Application
     * @description An application in full, with its job, form, requirements and replies.
     */
    Application: {
      /**
       * Answers
       * @default {}
       */
      answers: {
        [key: string]: unknown;
      };
      /** Applied At */
      applied_at?: string | null;
      /** Blocking Requirements */
      blocking_requirements: number;
      /** Concluded On */
      concluded_on?: string | null;
      /** Created At */
      created_at: string;
      /** Deadline */
      deadline?: string | null;
      /** Documents Count */
      documents_count: number;
      /**
       * From Shortlist
       * @default false
       */
      from_shortlist: boolean;
      /** Id */
      id: string;
      /** Job */
      job: components["schemas"]["Job"] | components["schemas"]["JobSummary"];
      /** Job Id */
      job_id: string;
      /** Last Reply */
      last_reply?: {
        [key: string]: unknown;
      } | null;
      /**
       * Missing
       * @description cv, letter and requirement:<id> still missing.
       */
      missing: string[];
      /** Open Requirements */
      open_requirements: number;
      /** Outcome */
      outcome?: string | null;
      pinned_note?: components["schemas"]["Note"] | null;
      /**
       * Preparation
       * @default []
       */
      preparation: {
        [key: string]: unknown;
      }[];
      /** Priority */
      priority?: number | null;
      /**
       * Questions
       * @default []
       */
      questions: {
        [key: string]: unknown;
      }[];
      /** Ready */
      ready: boolean;
      /**
       * Replies
       * @default []
       */
      replies: components["schemas"]["Reply"][];
      /** Required Documents */
      required_documents: string[];
      /**
       * Requirements
       * @default []
       */
      requirements: components["schemas"]["Requirement-Output"][];
      /** Status */
      status: string;
      /** Updated At */
      updated_at: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** ApplicationBulk */
    ApplicationBulk: {
      /**
       * Action
       * @enum {string}
       */
      action: "close" | "reopen" | "delete";
      /** Items */
      items: components["schemas"]["BulkItem"][];
      /** Outcome */
      outcome?:
        ("accepted" | "rejected" | "not_pursued" | "no_response") | null;
      /** Status */
      status?: ("shortlisted" | "applied" | "interview" | "offer") | null;
    };
    /**
     * ApplicationChange
     * @description The application after a change; its job is the compact summary.
     */
    ApplicationChange: {
      /**
       * Answers
       * @default {}
       */
      answers: {
        [key: string]: unknown;
      };
      /** Applied At */
      applied_at?: string | null;
      /** Blocking Requirements */
      blocking_requirements: number;
      /** Concluded On */
      concluded_on?: string | null;
      /** Created At */
      created_at: string;
      /** Deadline */
      deadline?: string | null;
      /** Documents Count */
      documents_count: number;
      /**
       * From Shortlist
       * @default false
       */
      from_shortlist: boolean;
      /** Id */
      id: string;
      /** Job */
      job: components["schemas"]["Job"] | components["schemas"]["JobSummary"];
      /** Job Id */
      job_id: string;
      /** Last Reply */
      last_reply?: {
        [key: string]: unknown;
      } | null;
      /**
       * Missing
       * @description cv, letter and requirement:<id> still missing.
       */
      missing: string[];
      /** Open Requirements */
      open_requirements: number;
      /** Outcome */
      outcome?: string | null;
      pinned_note?: components["schemas"]["Note"] | null;
      /**
       * Preparation
       * @default []
       */
      preparation: {
        [key: string]: unknown;
      }[];
      /** Priority */
      priority?: number | null;
      /**
       * Questions
       * @default []
       */
      questions: {
        [key: string]: unknown;
      }[];
      /** Ready */
      ready: boolean;
      /**
       * Replies
       * @default []
       */
      replies: components["schemas"]["Reply"][];
      /** Required Documents */
      required_documents: string[];
      /**
       * Requirements
       * @default []
       */
      requirements: components["schemas"]["Requirement-Output"][];
      /** Status */
      status: string;
      /** Updated At */
      updated_at: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** ApplicationInput */
    ApplicationInput: {
      /**
       * Deadline
       * @description Closing date as YYYY-MM-DD.
       */
      deadline?: string | null;
      /** Idempotency Key */
      idempotency_key?: string | null;
      /** Job Id */
      job_id: string;
      /** Priority */
      priority?: number | null;
      /** Questions */
      questions?: components["schemas"]["Question"][];
      /**
       * Required Documents
       * @description The documents Ready needs: a subset of cv and letter (both by default). Form answers never affect Ready.
       * @default [
       *       "cv",
       *       "letter"
       *     ]
       */
      required_documents: ("cv" | "letter")[];
      /** Requirements */
      requirements?: components["schemas"]["Requirement-Input"][];
    };
    /** ApplicationPage */
    ApplicationPage: {
      /** Items */
      items: components["schemas"]["ApplicationRow"][];
      /** Limit */
      limit?: number | null;
      no_reply?: components["schemas"]["NoReply"] | null;
      /** Offset */
      offset?: number | null;
      /** Stage Counts */
      stage_counts: {
        [key: string]: number;
      };
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** ApplicationPatch */
    ApplicationPatch: {
      /** Answers */
      answers?: {
        [key: string]: unknown;
      } | null;
      /** Applied At */
      applied_at?: string | null;
      /**
       * Concluded On
       * @description With outcome no_response: the day it was concluded that no reply will come (YYYY-MM-DD, not in the future); today (UTC) when omitted.
       */
      concluded_on?: string | null;
      /**
       * Deadline
       * @description Closing date as YYYY-MM-DD; null clears it.
       */
      deadline?: string | null;
      /** Expected Version */
      expected_version: number;
      /**
       * Outcome
       * @description Required to close: accepted, rejected (by the employer), not_pursued (stopped by the owner) or no_response (no answer within the no-reply period; only for a sent application).
       */
      outcome?:
        ("accepted" | "rejected" | "not_pursued" | "no_response") | null;
      /** Priority */
      priority?: number | null;
      /** Questions */
      questions?: components["schemas"]["Question"][] | null;
      /** @description Record an employer reply (kind, date, note) and move the stage with it in the same change: interview moves an Applied application to Interview, offer moves it to Offer, rejection closes it as rejected; other never moves the stage. A Closed application without a reply (no_response) is reopened the same way. With id: correct a reply's kind, date or note, or remove it (remove=true); a correction never moves the stage. */
      reply?: components["schemas"]["ReplyChange"] | null;
      /**
       * Required Documents
       * @description The documents Ready needs: a subset of cv and letter (both by default). Form answers never affect Ready.
       */
      required_documents?: ("cv" | "letter")[] | null;
      /**
       * Requirements
       * @description Replaces the whole requirement list; include existing ids to keep them.
       */
      requirements?: components["schemas"]["Requirement-Input"][] | null;
      /**
       * Status
       * @description applied is Mark applied (applied_at defaults to now); shortlisted again undoes it while the application has no reply, clearing applied_at. Record an employer reply with reply, which sets the stage itself.
       */
      status?:
        ("shortlisted" | "applied" | "interview" | "offer" | "closed") | null;
    };
    /** ApplicationRef */
    ApplicationRef: {
      /** Id */
      id: string;
      /** Outcome */
      outcome?: string | null;
      /** Status */
      status: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /**
     * ApplicationRow
     * @description An application as lists show it; ready and missing are computed.
     */
    ApplicationRow: {
      /** Applied At */
      applied_at?: string | null;
      /** Blocking Requirements */
      blocking_requirements: number;
      /** Concluded On */
      concluded_on?: string | null;
      /** Created At */
      created_at: string;
      /** Deadline */
      deadline?: string | null;
      /** Documents Count */
      documents_count: number;
      /** Id */
      id: string;
      /** Job */
      job: {
        [key: string]: unknown;
      };
      /** Job Id */
      job_id: string;
      /** Last Reply */
      last_reply?: {
        [key: string]: unknown;
      } | null;
      /**
       * Missing
       * @description cv, letter and requirement:<id> still missing.
       */
      missing: string[];
      /** Open Requirements */
      open_requirements: number;
      /** Outcome */
      outcome?: string | null;
      /**
       * Preparation
       * @default []
       */
      preparation: {
        [key: string]: unknown;
      }[];
      /** Priority */
      priority?: number | null;
      /** Ready */
      ready: boolean;
      /** Required Documents */
      required_documents: string[];
      /** Status */
      status: string;
      /** Updated At */
      updated_at: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** BackupList */
    BackupList: {
      /** Items */
      items: {
        [key: string]: unknown;
      }[];
      /** Schedule */
      schedule: {
        [key: string]: unknown;
      };
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** BatchItem */
    BatchItem: {
      /**
       * Error
       * @description The Error body of a failed item.
       */
      error?: {
        [key: string]: unknown;
      } | null;
      /** Id */
      id: string;
      /**
       * Index
       * @description The item's position in the request.
       */
      index: number;
      /** Ok */
      ok: boolean;
      /** Result */
      result?: {
        [key: string]: unknown;
      } | null;
      /**
       * Version
       * @description The record's version after a change.
       */
      version?: number | null;
    } & {
      [key: string]: unknown;
    };
    /**
     * BatchResult
     * @description One result per selected item; each item succeeds or fails on its own.
     */
    BatchResult: {
      /**
       * Batch Id
       * @description The batch of the recorded changes (events_list batch_id).
       */
      batch_id?: string | null;
      /** Failed */
      failed: number;
      /** Items */
      items: components["schemas"]["BatchItem"][];
      /** Succeeded */
      succeeded: number;
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** BulkItem */
    BulkItem: {
      /** Expected Version */
      expected_version: number;
      /** Id */
      id: string;
    };
    /** CareerDates */
    CareerDates: {
      /**
       * Current
       * @default false
       */
      current: boolean;
      /** End */
      end?: string | null;
      /**
       * Kind
       * @enum {string}
       */
      kind: "single" | "period";
      /** Start */
      start: string;
    };
    /** CareerImport */
    CareerImport: {
      /** Expected Profile Version */
      expected_profile_version?: number | null;
      /** Knowledge */
      knowledge?: components["schemas"]["KnowledgeCreate"][];
      /** Profile */
      profile?: {
        [key: string]: unknown;
      } | null;
    };
    /** Claim */
    Claim: {
      /** Always Include */
      always_include: boolean;
      /** Approved */
      approved: boolean;
      /** Created At */
      created_at: string;
      /** Id */
      id: string;
      /** Knowledge Id */
      knowledge_id: string;
      /** Metadata */
      metadata?: {
        [key: string]: unknown;
      } | null;
      /** Position */
      position: number;
      /** Text */
      text?: string | null;
      /** Text Preview */
      text_preview?: string | null;
      /** Updated At */
      updated_at: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** ClaimCreate */
    ClaimCreate: {
      /**
       * Always Include
       * @description Always include in the CV unless the job gives a reason to leave it out (★ in the dashboard).
       * @default false
       */
      always_include: boolean;
      /**
       * Approved
       * @default false
       */
      approved: boolean;
      /**
       * Idempotency Key
       * @description Retrying with the same key and request returns the record the first request created.
       */
      idempotency_key?: string | null;
      /** Knowledge Id */
      knowledge_id: string;
      /**
       * Metadata
       * @description Free-form values the product does not act on, such as an agent's own selection hints.
       */
      metadata?: {
        [key: string]: unknown;
      };
      /** Position */
      position?: number | null;
      /** Text */
      text: string;
    };
    /** ClaimPage */
    ClaimPage: {
      /** Items */
      items: components["schemas"]["Claim"][];
      /** Limit */
      limit?: number | null;
      /** Offset */
      offset?: number | null;
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** ClaimUpdate */
    ClaimUpdate: {
      /** Always Include */
      always_include?: boolean | null;
      /** Approved */
      approved?: boolean | null;
      /** Expected Version */
      expected_version: number;
      /** Knowledge Id */
      knowledge_id?: string | null;
      /** Metadata */
      metadata?: {
        [key: string]: unknown;
      } | null;
      /** Position */
      position?: number | null;
      /** Text */
      text?: string | null;
    };
    /** Collection */
    Collection: {
      /** Enabled */
      enabled: boolean;
      /** Enabled Sources */
      enabled_sources: number;
      /** Next Run At */
      next_run_at?: string | null;
      /** Queued Tasks */
      queued_tasks: number;
      /** Running Tasks */
      running_tasks: number;
      /** Source Count */
      source_count: number;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** CollectionRun */
    CollectionRun: {
      /**
       * Counts
       * @default {}
       */
      counts: {
        [key: string]: unknown;
      };
      /** Created At */
      created_at: string;
      /** Finished At */
      finished_at?: string | null;
      /** Http Requests */
      http_requests?: number | null;
      /** Id */
      id: string;
      /** Next Run At */
      next_run_at?: string | null;
      /** Partial */
      partial?: boolean | null;
      /** Source Id */
      source_id?: string | null;
      /** Source Name */
      source_name?: string | null;
      /** Source Version */
      source_version?: number | null;
      /** Started At */
      started_at?: string | null;
      /** State */
      state: string;
      /**
       * Task Ids
       * @default []
       */
      task_ids: string[];
      /**
       * Tasks
       * @default []
       */
      tasks: {
        [key: string]: unknown;
      }[];
    } & {
      [key: string]: unknown;
    };
    /** CollectionRunPage */
    CollectionRunPage: {
      /** Items */
      items: components["schemas"]["CollectionRun"][];
      /** Limit */
      limit?: number | null;
      /** Offset */
      offset?: number | null;
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** CollectionWrite */
    CollectionWrite: {
      /** Enabled */
      enabled: boolean;
      /** Expected Version */
      expected_version: number;
    };
    /** Comparison */
    Comparison: {
      /** Added */
      added: number;
      /** Document Id */
      document_id: string;
      /** Lines */
      lines: {
        [key: string]: unknown;
      }[];
      /** Other Id */
      other_id?: string | null;
      /** Removed */
      removed: number;
      /** Text */
      text: {
        [key: string]: unknown;
      };
    } & {
      [key: string]: unknown;
    };
    /** DailySchedule */
    DailySchedule: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      kind: "daily";
      /** Times */
      times?: string[];
      /**
       * Timezone
       * @default UTC
       */
      timezone: string;
    };
    /**
     * Deleted
     * @description A permanent deletion.
     */
    Deleted: {
      /** Deleted */
      deleted: boolean;
      /** Id */
      id?: string | null;
      /** Name */
      name?: string | null;
    } & {
      [key: string]: unknown;
    };
    /** Dismissal */
    Dismissal: {
      /** At */
      at?: string | null;
      /** By */
      by?: string | null;
      /** Category */
      category: string;
      /**
       * Reason
       * @default
       */
      reason: string;
    } & {
      [key: string]: unknown;
    };
    /** DistinctInput */
    DistinctInput: {
      /**
       * Other Id
       * @description The job flagged as its likely duplicate that is in fact a different vacancy.
       */
      other_id: string;
    };
    /** Document */
    Document: {
      /** Application Id */
      application_id: string;
      /**
       * Claim Ids
       * @default []
       */
      claim_ids: string[];
      /**
       * Complete
       * @description A CV or letter whose PDF is stored.
       */
      complete: boolean;
      /** Content */
      content?: {
        [key: string]: unknown;
      } | null;
      /** Created At */
      created_at: string;
      /** File Count */
      file_count?: number | null;
      /**
       * Files
       * @default []
       */
      files: components["schemas"]["WorkspaceFile"][];
      /** Id */
      id: string;
      /** Kind */
      kind: string;
      /**
       * Knowledge Ids
       * @default []
       */
      knowledge_ids: string[];
      /**
       * Note
       * @default
       */
      note: string;
      /** Previous Id */
      previous_id?: string | null;
      /** Revision Number */
      revision_number: number;
      /** Source Sha256 */
      source_sha256?: string | null;
      /** Text */
      text?: string | null;
      /**
       * Text From
       * @description tex or pdf
       */
      text_from?: string | null;
      /** Title */
      title: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** DocumentCreate */
    DocumentCreate: {
      /** Application Id */
      application_id: string;
      /**
       * Claim Ids
       * @description Approved claims the revision uses.
       */
      claim_ids?: string[];
      /**
       * Content
       * @description Structured content of form answers or another document. Not accepted for a CV or letter (cv, letter): those are a PDF and an optional TeX source.
       */
      content?: {
        [key: string]: unknown;
      } | null;
      /**
       * Idempotency Key
       * @description Retrying with the same key and request returns the record the first request created.
       */
      idempotency_key?: string | null;
      /**
       * Kind
       * @default cv
       * @enum {string}
       */
      kind: "cv" | "letter" | "answers" | "other";
      /**
       * Knowledge Ids
       * @description Career entries the revision uses.
       */
      knowledge_ids?: string[];
      /**
       * Note
       * @description An optional note on the revision.
       * @default
       */
      note: string;
      /** @description CV or letter: the PDF to upload. The result's uploads.pdf is a one-shot grant: PUT the exact bytes to its url with its headers. The revision is incomplete until its PDF is stored, then complete and immutable. */
      pdf?: components["schemas"]["FileSpec"] | null;
      /** Previous Id */
      previous_id?: string | null;
      /**
       * Source
       * @description CV or letter, optional: the TeX source inline (UTF-8, at most 256 KB). Its readable text is derived from it; the PDF must then be built from it (the PDF grant names its SHA-256).
       */
      source?: string | null;
      /** @description CV or letter, optional, instead of source: a .tex file to upload with the grant uploads.source, before the PDF. */
      source_file?: components["schemas"]["FileSpec"] | null;
      /**
       * Title
       * @default
       */
      title: string;
    };
    /** DocumentPage */
    DocumentPage: {
      /** Items */
      items: components["schemas"]["Document"][];
      /** Limit */
      limit?: number | null;
      /** Offset */
      offset?: number | null;
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** DuplicateGroup */
    DuplicateGroup: {
      /** Confidence */
      confidence: number;
      /** Identical Postings */
      identical_postings: boolean;
      /** Items */
      items: {
        [key: string]: unknown;
      }[];
      /** Job Ids */
      job_ids: string[];
      /** Merge Blocked */
      merge_blocked: boolean;
      /**
       * Open Application Ids
       * @default []
       */
      open_application_ids: string[];
      /**
       * Reasons
       * @default {}
       */
      reasons: {
        [key: string]: unknown;
      };
      /** Reference Id */
      reference_id: string;
      /**
       * Signals
       * @default []
       */
      signals: string[];
      /** Size */
      size: number;
      /** Tier */
      tier: string;
    } & {
      [key: string]: unknown;
    };
    /** DuplicatePage */
    DuplicatePage: {
      /** Items */
      items: components["schemas"]["DuplicateGroup"][];
      /** Limit */
      limit?: number | null;
      /** Min Confidence */
      min_confidence: number;
      /** Offset */
      offset?: number | null;
      /** Tiers */
      tiers: {
        [key: string]: number;
      };
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /**
     * Error
     * @description Every error response. Codes by status: 401 unauthorized: sign in or send a valid bearer token (also transfer_token, transfer_expired). 403 forbidden: an agent token on an owner-only operation; csrf: a browser write without its X-CSRF-Token header. 404 not_found: the record or route does not exist. 409 conflict: the record changed (details.current_version and details.id); also constraint, application_has_work and similar rule conflicts. 410 removed: a route removed in 0.24; details.use names its replacement. 413 request_size or file_size: the body or file is over its limit. 422 validation: details lists {field, message, type} per invalid field; other codes name a rule. 429 rate_limited: the shared provider gate is waiting; details.retry_after_seconds and the Retry-After header give the wait.
     */
    Error: {
      error: components["schemas"]["ErrorBody"];
    };
    /** ErrorBody */
    ErrorBody: {
      /**
       * Code
       * @description A stable machine code, such as validation or conflict.
       */
      code: string;
      /**
       * Details
       * @description Structured details: field errors for validation, current_version and id for a version conflict, use for a removed route.
       */
      details?: unknown;
      /**
       * Message
       * @description A sentence for a person.
       */
      message: string;
      /**
       * Status
       * @description The HTTP status.
       */
      status: number;
    };
    /** Event */
    Event: {
      /** Actor */
      actor?: string | null;
      /** Application Id */
      application_id?: string | null;
      /** Batch Id */
      batch_id?: string | null;
      /** Created At */
      created_at: string;
      /** Id */
      id: string;
      /** Job Id */
      job_id?: string | null;
      /** Kind */
      kind: string;
      /**
       * Payload
       * @default {}
       */
      payload: {
        [key: string]: unknown;
      };
      /** Subject */
      subject?: {
        [key: string]: unknown;
      } | null;
    } & {
      [key: string]: unknown;
    };
    /** EventPage */
    EventPage: {
      /** Items */
      items: components["schemas"]["Event"][];
      /** Limit */
      limit?: number | null;
      /** Offset */
      offset?: number | null;
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** FileGrant */
    FileGrant: {
      /** Expires At */
      expires_at: string;
      /** Headers */
      headers: {
        [key: string]: string;
      };
      /** Max Bytes */
      max_bytes?: number | null;
      /** Method */
      method: string;
      /** Url */
      url: string;
    } & {
      [key: string]: unknown;
    };
    /** FilePage */
    FilePage: {
      /** Items */
      items: components["schemas"]["WorkspaceFile"][];
      /** Limit */
      limit?: number | null;
      /** Offset */
      offset?: number | null;
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /**
     * FileSpec
     * @description A file to upload with a grant the create returns: its name, size and, optionally, hash.
     */
    FileSpec: {
      /** Name */
      name: string;
      /** Sha256 */
      sha256?: string | null;
      /** Size */
      size: number;
    };
    /** Filters */
    Filters: {
      /** Exclude Titles */
      exclude_titles?: string[];
      /** Locations */
      locations?: string[];
      /** Titles */
      titles?: string[];
    };
    /** ImportPreview */
    ImportPreview: {
      /** Text */
      text: string;
      /**
       * Title
       * @default Imported career notes
       */
      title: string;
    };
    /** ImportPreviewResult */
    ImportPreviewResult: {
      /** Knowledge */
      knowledge: {
        [key: string]: unknown;
      }[];
      /** Profile */
      profile?: {
        [key: string]: unknown;
      } | null;
      /**
       * Warnings
       * @default []
       */
      warnings: unknown[];
    } & {
      [key: string]: unknown;
    };
    /** ImportResult */
    ImportResult: {
      /** Items */
      items: components["schemas"]["Knowledge"][];
      profile?: components["schemas"]["Profile"] | null;
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** IntervalSchedule */
    IntervalSchedule: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      kind: "interval";
      /**
       * Minutes
       * @default 1440
       */
      minutes: number;
    };
    /**
     * Job
     * @description A job in full: the posting, its overrides and every observation.
     */
    Job: {
      application?: components["schemas"]["ApplicationRef"] | null;
      /** Application Count */
      application_count: number;
      /** Company */
      company: string;
      /** Complete */
      complete: boolean;
      /** Content Version */
      content_version?: number | null;
      /**
       * Created
       * @description On jobs_create: a new job.
       */
      created?: boolean | null;
      /** Created At */
      created_at: string;
      dismissal?: components["schemas"]["Dismissal"] | null;
      /** Id */
      id: string;
      /** Job Type */
      job_type?: string | null;
      /** Location */
      location: string;
      /**
       * Metadata
       * @default {}
       */
      metadata: {
        [key: string]: unknown;
      };
      /**
       * Overrides
       * @default {}
       */
      overrides: {
        [key: string]: unknown;
      };
      /** Posting */
      posting: string;
      /** Posting Preview */
      posting_preview?: string | null;
      /**
       * Postings
       * @default []
       */
      postings: components["schemas"]["Observation"][];
      signals: components["schemas"]["Signals"];
      /** Source */
      source?: string | null;
      /** Title */
      title: string;
      /** Triage */
      triage: string;
      /** Updated At */
      updated_at?: string | null;
      /** Url */
      url: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** JobBulk */
    JobBulk: {
      /**
       * Action
       * @enum {string}
       */
      action: "shortlisted" | "dismissed" | "new" | "forget";
      /** Items */
      items: components["schemas"]["BulkItem"][];
      /**
       * Reason
       * @description With dismissed: why, in a short sentence, shown in the Dismissed list (for example 'Junior role; I look for senior roles').
       */
      reason?: string | null;
    };
    /** JobCounts */
    JobCounts: {
      /** All */
      all: number;
      /** Dismissed */
      dismissed: number;
      /** Dismissed By */
      dismissed_by: {
        [key: string]: number;
      };
      /** New */
      new: number;
      /** Shortlisted */
      shortlisted: number;
    } & {
      [key: string]: unknown;
    };
    /** JobInput */
    JobInput: {
      /**
       * Company
       * @default
       */
      company: string;
      /**
       * Idempotency Key
       * @description Retrying with the same key and request returns the record the first request created.
       */
      idempotency_key?: string | null;
      /**
       * Location
       * @default
       */
      location: string;
      /** Metadata */
      metadata?: {
        [key: string]: unknown;
      };
      /**
       * Posting
       * @default
       */
      posting: string;
      /** Raw */
      raw?: {
        [key: string]: unknown;
      };
      /** Source Id */
      source_id?: string | null;
      /** Source Key */
      source_key?: string | null;
      /**
       * Title
       * @default
       */
      title: string;
      /**
       * Url
       * @default
       */
      url: string;
    };
    /** JobPage */
    JobPage: {
      counts?: components["schemas"]["JobCounts"] | null;
      /** Facets */
      facets?: {
        [key: string]: string[];
      } | null;
      /** Items */
      items: components["schemas"]["JobSummary"][];
      /** Limit */
      limit?: number | null;
      /** Offset */
      offset?: number | null;
      /** Total */
      total: number;
      /** Unspoken Required */
      unspoken_required?: {
        [key: string]: unknown;
      } | null;
    } & {
      [key: string]: unknown;
    };
    /** JobPatch */
    JobPatch: {
      /** Company */
      company?: string | null;
      /** Expected Version */
      expected_version: number;
      /** Location */
      location?: string | null;
      /** Metadata */
      metadata?: {
        [key: string]: unknown;
      } | null;
      /** Posting */
      posting?: string | null;
      /** Title */
      title?: string | null;
      /** Url */
      url?: string | null;
    };
    /**
     * JobSummary
     * @description A compact job: list rows and the result of a change.
     */
    JobSummary: {
      application?: components["schemas"]["ApplicationRef"] | null;
      /** Application Count */
      application_count: number;
      /** Company */
      company: string;
      /** Complete */
      complete: boolean;
      /** Content Version */
      content_version?: number | null;
      /** Created At */
      created_at: string;
      dismissal?: components["schemas"]["Dismissal"] | null;
      /** Id */
      id: string;
      /** Job Type */
      job_type?: string | null;
      /** Location */
      location: string;
      /**
       * Metadata
       * @default {}
       */
      metadata: {
        [key: string]: unknown;
      };
      /** Posting Preview */
      posting_preview?: string | null;
      signals: components["schemas"]["Signals"];
      /** Source */
      source?: string | null;
      /** Title */
      title: string;
      /** Triage */
      triage: string;
      /** Updated At */
      updated_at?: string | null;
      /** Url */
      url: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** Knowledge */
    Knowledge: {
      /** Claim Count */
      claim_count?: number | null;
      /** Created At */
      created_at: string;
      /** Dates */
      dates?: {
        [key: string]: unknown;
      } | null;
      /** File Count */
      file_count?: number | null;
      /** Id */
      id: string;
      /** Kind */
      kind: string;
      /** Metadata */
      metadata?: {
        [key: string]: unknown;
      } | null;
      /** Narrative */
      narrative?: string | null;
      /** Narrative Preview */
      narrative_preview?: string | null;
      /** Organization */
      organization: string;
      /** Position */
      position: number;
      /**
       * Skills
       * @default []
       */
      skills: string[];
      /** Title */
      title: string;
      /** Updated At */
      updated_at: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** KnowledgeCreate */
    KnowledgeCreate: {
      dates?: components["schemas"]["CareerDates"] | null;
      /**
       * Idempotency Key
       * @description Retrying with the same key and request returns the record the first request created.
       */
      idempotency_key?: string | null;
      /**
       * Kind
       * @default experience
       * @enum {string}
       */
      kind:
        | "experience"
        | "project"
        | "course"
        | "education"
        | "award"
        | "publication"
        | "fact"
        | "skill"
        | "language"
        | "other";
      /** Metadata */
      metadata?: {
        [key: string]: unknown;
      };
      /**
       * Narrative
       * @default
       */
      narrative: string;
      /**
       * Organization
       * @default
       */
      organization: string;
      /** Position */
      position?: number | null;
      /** Skills */
      skills?: string[];
      /** Title */
      title: string;
    };
    /** KnowledgePage */
    KnowledgePage: {
      /** Items */
      items: components["schemas"]["Knowledge"][];
      /** Limit */
      limit?: number | null;
      /** Offset */
      offset?: number | null;
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** KnowledgeUpdate */
    KnowledgeUpdate: {
      dates?: components["schemas"]["CareerDates"] | null;
      /** Expected Version */
      expected_version: number;
      /** Kind */
      kind?:
        | (
            | "experience"
            | "project"
            | "course"
            | "education"
            | "award"
            | "publication"
            | "fact"
            | "skill"
            | "language"
            | "other"
          )
        | null;
      /** Metadata */
      metadata?: {
        [key: string]: unknown;
      } | null;
      /** Narrative */
      narrative?: string | null;
      /** Organization */
      organization?: string | null;
      /** Position */
      position?: number | null;
      /** Skills */
      skills?: string[] | null;
      /** Title */
      title?: string | null;
    };
    /** MergeInput */
    MergeInput: {
      /** Expected Version */
      expected_version: number;
      /** Target Id */
      target_id: string;
      /** Target Version */
      target_version: number;
    };
    /** NewDocument */
    NewDocument: {
      /** Application Id */
      application_id: string;
      /**
       * Claim Ids
       * @default []
       */
      claim_ids: string[];
      /**
       * Complete
       * @description A CV or letter whose PDF is stored.
       */
      complete: boolean;
      /** Content */
      content?: {
        [key: string]: unknown;
      } | null;
      /** Created At */
      created_at: string;
      /** File Count */
      file_count?: number | null;
      /**
       * Files
       * @default []
       */
      files: components["schemas"]["WorkspaceFile"][];
      /** Id */
      id: string;
      /** Kind */
      kind: string;
      /**
       * Knowledge Ids
       * @default []
       */
      knowledge_ids: string[];
      /**
       * Note
       * @default
       */
      note: string;
      /** Previous Id */
      previous_id?: string | null;
      /** Revision Number */
      revision_number: number;
      /** Source Sha256 */
      source_sha256?: string | null;
      /** Text */
      text?: string | null;
      /**
       * Text From
       * @description tex or pdf
       */
      text_from?: string | null;
      /** Title */
      title: string;
      /** @description CV or letter: PUT each file's bytes with its grant. */
      uploads?: components["schemas"]["Uploads"] | null;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** NoReply */
    NoReply: {
      /** Days */
      days: number;
      /** Overdue */
      overdue?: number | null;
      /** Source */
      source: string;
    } & {
      [key: string]: unknown;
    };
    /** Note */
    Note: {
      /** Application Id */
      application_id?: string | null;
      /** Author */
      author?: string | null;
      /** Body */
      body: string;
      /** Created At */
      created_at: string;
      /** Id */
      id: string;
      /** Job Id */
      job_id: string;
      /** Pinned */
      pinned: boolean;
      /** Pinned At */
      pinned_at?: string | null;
      /**
       * Scope
       * @description job or application
       */
      scope: string;
      /** Updated At */
      updated_at: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** NoteInput */
    NoteInput: {
      /**
       * Application Id
       * @description Write the note on this application of the job; omit for a note on the job itself.
       */
      application_id?: string | null;
      /** Body */
      body: string;
      /**
       * Idempotency Key
       * @description Retrying with the same key and request returns the record the first request created.
       */
      idempotency_key?: string | null;
      /**
       * Pinned
       * @description Pin the note: it is listed first in its timeline. A job and an application each have at most one pinned note; pinning another unpins it.
       * @default false
       */
      pinned: boolean;
    };
    /** NoteList */
    NoteList: {
      /** Items */
      items: components["schemas"]["Note"][];
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** NotePatch */
    NotePatch: {
      /** Body */
      body: string;
      /** Expected Version */
      expected_version: number;
    };
    /** NotePin */
    NotePin: {
      /** Expected Version */
      expected_version: number;
      /**
       * Pinned
       * @description True pins the note (unpinning the note pinned in the same scope); false unpins it.
       * @default true
       */
      pinned: boolean;
    };
    /** Observation */
    Observation: {
      /** First Seen At */
      first_seen_at: string;
      /** Id */
      id: string;
      /** Identity */
      identity: string;
      /** Last Seen At */
      last_seen_at: string;
      /** Source Id */
      source_id?: string | null;
      /** Source Kind */
      source_kind?: string | null;
      /** Source Name */
      source_name?: string | null;
      /** Unlisted At */
      unlisted_at?: string | null;
      /** Url */
      url: string;
    } & {
      [key: string]: unknown;
    };
    /** OperationGrant */
    OperationGrant: {
      /** Expires In */
      expires_in: number;
      /** Headers */
      headers: {
        [key: string]: string;
      };
      /** Method */
      method: string;
      /** Url */
      url: string;
    } & {
      [key: string]: unknown;
    };
    /** PasswordChanged */
    PasswordChanged: {
      /** Api Tokens Preserved */
      api_tokens_preserved: boolean;
      /** Sign In Required */
      sign_in_required: boolean;
      /** Updated */
      updated: boolean;
    } & {
      [key: string]: unknown;
    };
    /** PasswordInput */
    PasswordInput: {
      /** Password */
      password: string;
    };
    /** PreferenceItem */
    PreferenceItem: {
      /**
       * Scope
       * @description Writing rules only: all (the default), cv or letter. Other sections take none.
       */
      scope?: ("all" | "cv" | "letter") | null;
      /**
       * Text
       * @description The statement in the owner's words.
       */
      text: string;
    };
    /** Preferences */
    Preferences: {
      /** Sections */
      sections: components["schemas"]["PreferenceSection"][];
      settings: components["schemas"]["Settings"];
    } & {
      [key: string]: unknown;
    };
    /** PreferenceSection */
    PreferenceSection: {
      /** Description */
      description: string;
      /**
       * Items
       * @description {text} and, in writing, {text, scope}.
       */
      items: {
        [key: string]: unknown;
      }[];
      /** Section */
      section: string;
      /** Title */
      title: string;
      /** Updated At */
      updated_at?: string | null;
      /** Updated By */
      updated_by?: string | null;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /**
     * PreferencesUpdate
     * @description The whole new list of a section's statements, in order.
     */
    PreferencesUpdate: {
      /**
       * Expected Version
       * @description The section's current version.
       */
      expected_version: number;
      /**
       * Items
       * @description Every statement of the section, in order (at most 200, each at most 2000 characters): {text, scope}.
       */
      items: components["schemas"]["PreferenceItem"][];
    };
    /** Profile */
    Profile: {
      /** Email */
      email: string;
      /** Headline */
      headline: string;
      /**
       * Links
       * @default []
       */
      links: {
        [key: string]: unknown;
      }[];
      /** Location */
      location: string;
      /**
       * Metadata
       * @default {}
       */
      metadata: {
        [key: string]: unknown;
      };
      /** Name */
      name: string;
      /** Phone */
      phone: string;
      /** Summary */
      summary: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** ProfileUpdate */
    ProfileUpdate: {
      /** Email */
      email?: string | null;
      /** Expected Version */
      expected_version: number;
      /** Headline */
      headline?: string | null;
      /** Links */
      links?:
        | {
            [key: string]: string;
          }[]
        | null;
      /** Location */
      location?: string | null;
      /**
       * Metadata
       * @description Free-form extension values. What the owner wants, facts employers ask about and writing rules belong in Preferences.
       */
      metadata?: {
        [key: string]: unknown;
      } | null;
      /** Name */
      name?: string | null;
      /** Phone */
      phone?: string | null;
      /** Summary */
      summary?: string | null;
    };
    /** Provider */
    Provider: {
      /** Capability */
      capability: {
        [key: string]: unknown;
      };
      /** Id */
      id: string;
      /** Name */
      name: string;
      /** Policy */
      policy: {
        [key: string]: unknown;
      };
      /** Runtime */
      runtime: {
        [key: string]: unknown;
      };
      /** Updated At */
      updated_at?: string | null;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** ProviderList */
    ProviderList: {
      /** Items */
      items: components["schemas"]["Provider"][];
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** ProviderPatch */
    ProviderPatch: {
      /** Enabled */
      enabled?: boolean | null;
      /** Expected Version */
      expected_version: number;
      /** Min Interval Seconds */
      min_interval_seconds?: number | null;
    };
    /** Question */
    Question: {
      /** Id */
      id: string;
      /** Label */
      label: string;
      /** Max Length */
      max_length?: number | null;
      /** Options */
      options?: string[];
      /**
       * Required
       * @default false
       */
      required: boolean;
      /**
       * Type
       * @default text
       * @enum {string}
       */
      type: "text" | "choice" | "boolean" | "number";
    };
    /** Reply */
    Reply: {
      /** Application Id */
      application_id: string;
      /** Created At */
      created_at: string;
      /** Created By */
      created_by?: string | null;
      /** Date */
      date: string;
      /** Id */
      id: string;
      /** Job Id */
      job_id?: string | null;
      /** Kind */
      kind: string;
      /**
       * Note
       * @default
       */
      note: string;
      /** Updated At */
      updated_at: string;
      /** Updated By */
      updated_by?: string | null;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /**
     * ReplyChange
     * @description An employer reply to record, correct or remove.
     */
    ReplyChange: {
      /**
       * Date
       * @description The day it arrived (YYYY-MM-DD, not in the future); today (UTC) for a new reply when omitted.
       */
      date?: string | null;
      /**
       * Id
       * @description The reply to correct or remove; omit to record a new reply.
       */
      id?: string | null;
      /**
       * Kind
       * @description interview (an invitation), rejection, offer or other (any other answer). Required for a new reply.
       */
      kind?: ("interview" | "rejection" | "offer" | "other") | null;
      /** Note */
      note?: string | null;
      /**
       * Remove
       * @description With id: delete a reply recorded by mistake.
       * @default false
       */
      remove: boolean;
    };
    /**
     * Requirement
     * @description One employer requirement found in a posting or application form.
     */
    "Requirement-Input": {
      /**
       * Blocking
       * @description True when documents must not be prepared or submitted until it is resolved.
       * @default false
       */
      blocking: boolean;
      /**
       * Id
       * @description Stable identifier; assigned when omitted.
       */
      id?: string | null;
      /**
       * Kind
       * @default other
       * @enum {string}
       */
      kind:
        | "authorship"
        | "attachment"
        | "reference"
        | "format"
        | "language"
        | "eligibility"
        | "deadline"
        | "other";
      /**
       * Note
       * @description Resolution, owner decision or open question.
       * @default
       */
      note: string;
      /**
       * Resolved
       * @default false
       */
      resolved: boolean;
      /**
       * Text
       * @description The requirement as stated.
       */
      text: string;
    };
    /** Requirement */
    "Requirement-Output": {
      /** Blocking */
      blocking: boolean;
      /** Id */
      id: string;
      /** Kind */
      kind: string;
      /**
       * Note
       * @default
       */
      note: string;
      /** Resolved */
      resolved: boolean;
      /** Text */
      text: string;
    } & {
      [key: string]: unknown;
    };
    /** ResolvedJob */
    ResolvedJob: {
      application?: components["schemas"]["ApplicationRef"] | null;
      /** Application Count */
      application_count: number;
      /**
       * Applications
       * @default []
       */
      applications: {
        [key: string]: unknown;
      }[];
      /** Company */
      company: string;
      /** Complete */
      complete: boolean;
      /** Content Version */
      content_version?: number | null;
      /** Created At */
      created_at: string;
      dismissal?: components["schemas"]["Dismissal"] | null;
      /** Id */
      id: string;
      /** Job Type */
      job_type?: string | null;
      /** Location */
      location: string;
      /** Matched By */
      matched_by: string[];
      /**
       * Metadata
       * @default {}
       */
      metadata: {
        [key: string]: unknown;
      };
      /** Posting Preview */
      posting_preview?: string | null;
      signals: components["schemas"]["Signals"];
      /** Source */
      source?: string | null;
      /** Title */
      title: string;
      /** Triage */
      triage: string;
      /** Updated At */
      updated_at?: string | null;
      /** Url */
      url: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** ResolvedJobs */
    ResolvedJobs: {
      /**
       * Identities
       * @default []
       */
      identities: string[];
      /**
       * Identity Conflict
       * @default false
       */
      identity_conflict: boolean;
      /** Items */
      items: components["schemas"]["ResolvedJob"][];
      /** Total */
      total: number;
      /** Url */
      url?: string | null;
    } & {
      [key: string]: unknown;
    };
    /** RunOverrides */
    RunOverrides: {
      /** Hours Old */
      hours_old?: number | null;
      /** Max Results */
      max_results?: number | null;
      /** Results Wanted */
      results_wanted?: number | null;
    };
    /** Settings */
    Settings: {
      /** No Reply Days */
      no_reply_days: number;
      /** Spoken Languages */
      spoken_languages: string[];
      /** Updated At */
      updated_at?: string | null;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /**
     * SettingsUpdate
     * @description Omitted settings stay as they are.
     */
    SettingsUpdate: {
      /**
       * Expected Version
       * @description The settings' current version (0 before the first save).
       */
      expected_version: number;
      /**
       * No Reply Days
       * @description Days after which an application without an employer answer counts as no reply.
       */
      no_reply_days?: number | null;
      /**
       * Spoken Languages
       * @description Languages the owner speaks, as ISO 639-1 codes such as en or de (English names are accepted).
       */
      spoken_languages?: string[] | null;
    };
    /** Signals */
    Signals: {
      /** Computed */
      computed: boolean;
      /**
       * Duplicate
       * @description {job_id, confidence, tier}
       */
      duplicate?: {
        [key: string]: unknown;
      } | null;
      /** Duplicate Checked */
      duplicate_checked: boolean;
      /** Language */
      language?: string | null;
      /** Language Confidence */
      language_confidence?: number | null;
      /** No Longer Listed */
      no_longer_listed: boolean;
      /**
       * Required
       * @description Groups of language codes; one language of a group is enough.
       * @default []
       */
      required: string[][];
      /** Unlisted At */
      unlisted_at?: string | null;
    } & {
      [key: string]: unknown;
    };
    /** Skill */
    Skill: {
      /** Content */
      content: string;
      /** Name */
      name: string;
      /** Path */
      path: string;
    } & {
      [key: string]: unknown;
    };
    /** SkillList */
    SkillList: {
      /** Items */
      items: components["schemas"]["SkillSummary"][];
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** SkillSummary */
    SkillSummary: {
      /** Description */
      description: string;
      /** Example */
      example: string;
      /**
       * File Details
       * @default []
       */
      file_details: {
        [key: string]: unknown;
      }[];
      /** Files */
      files: string[];
      /** Name */
      name: string;
      /** Summary */
      summary: string;
      /** Title */
      title: string;
    } & {
      [key: string]: unknown;
    };
    /** Source */
    Source: {
      /** Automatic Collection */
      automatic_collection: boolean;
      /** Config */
      config: {
        [key: string]: unknown;
      };
      /**
       * Counts
       * @description Jobs found, shortlisted, applied and replied.
       * @default {}
       */
      counts: {
        [key: string]: number;
      };
      /** Created At */
      created_at: string;
      /** Enabled */
      enabled: boolean;
      /** Filters */
      filters: {
        [key: string]: unknown;
      };
      /** Id */
      id: string;
      /** Kind */
      kind: string;
      /** Last Error */
      last_error?: string | null;
      /** Last Outcome */
      last_outcome?: string | null;
      /** Last Run */
      last_run?: {
        [key: string]: unknown;
      } | null;
      /** Name */
      name: string;
      /** Next Run At */
      next_run_at?: string | null;
      /** Schedule */
      schedule: {
        [key: string]: unknown;
      };
      /** Updated At */
      updated_at: string;
      /** Url */
      url: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** SourceBulk */
    SourceBulk: {
      /**
       * Action
       * @enum {string}
       */
      action: "enable" | "pause" | "run" | "delete" | "configure";
      /** Items */
      items: components["schemas"]["SourceVersion"][];
      overrides?: components["schemas"]["RunOverrides"];
      patch?: components["schemas"]["SourceConfigure"] | null;
    };
    /** SourceConfigure */
    SourceConfigure: {
      /** Config */
      config?: {
        [key: string]: unknown;
      } | null;
      filters?: components["schemas"]["Filters"] | null;
      /** Schedule */
      schedule?:
        | (
            | components["schemas"]["IntervalSchedule"]
            | components["schemas"]["DailySchedule"]
          )
        | null;
    };
    /** SourceCreate */
    SourceCreate: {
      /** Config */
      config?: {
        [key: string]: unknown;
      };
      /**
       * Enabled
       * @default false
       */
      enabled: boolean;
      filters?: components["schemas"]["Filters"];
      /**
       * Idempotency Key
       * @description Retrying with the same key and request returns the record the first request created.
       */
      idempotency_key?: string | null;
      /**
       * Kind
       * @default auto
       * @enum {string}
       */
      kind:
        | "auto"
        | "jobspy"
        | "rss"
        | "greenhouse"
        | "lever"
        | "ashby"
        | "recruitee"
        | "personio"
        | "workable"
        | "breezy"
        | "smartrecruiters"
        | "bamboohr"
        | "rippling"
        | "workday"
        | "oracle"
        | "joincom";
      /**
       * Name
       * @default
       */
      name: string;
      /** Schedule */
      schedule?:
        | components["schemas"]["IntervalSchedule"]
        | components["schemas"]["DailySchedule"];
      /**
       * Url
       * @default
       */
      url: string;
    };
    /** SourcePage */
    SourcePage: {
      /** Items */
      items: components["schemas"]["Source"][];
      /** Limit */
      limit?: number | null;
      /** Offset */
      offset?: number | null;
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** SourcePatch */
    SourcePatch: {
      /** Config */
      config?: {
        [key: string]: unknown;
      } | null;
      /** Enabled */
      enabled?: boolean | null;
      /** Expected Version */
      expected_version: number;
      filters?: components["schemas"]["Filters"] | null;
      /** Kind */
      kind?:
        | (
            | "auto"
            | "jobspy"
            | "rss"
            | "greenhouse"
            | "lever"
            | "ashby"
            | "recruitee"
            | "personio"
            | "workable"
            | "breezy"
            | "smartrecruiters"
            | "bamboohr"
            | "rippling"
            | "workday"
            | "oracle"
            | "joincom"
          )
        | null;
      /** Name */
      name?: string | null;
      /** Schedule */
      schedule?:
        | (
            | components["schemas"]["IntervalSchedule"]
            | components["schemas"]["DailySchedule"]
          )
        | null;
      /** Url */
      url?: string | null;
    };
    /** SourcePreview */
    SourcePreview: {
      /** Config */
      config?: {
        [key: string]: unknown;
      };
      filters?: components["schemas"]["Filters"];
      /**
       * Kind
       * @default auto
       * @enum {string}
       */
      kind:
        | "auto"
        | "jobspy"
        | "rss"
        | "greenhouse"
        | "lever"
        | "ashby"
        | "recruitee"
        | "personio"
        | "workable"
        | "breezy"
        | "smartrecruiters"
        | "bamboohr"
        | "rippling"
        | "workday"
        | "oracle"
        | "joincom";
      /**
       * Name
       * @default
       */
      name: string;
      /**
       * Url
       * @default
       */
      url: string;
    };
    /** SourcePreviewResult */
    SourcePreviewResult: {
      /**
       * Diagnostics
       * @default []
       */
      diagnostics: {
        [key: string]: unknown;
      }[];
      /** Items */
      items: {
        [key: string]: unknown;
      }[];
      /** Preview Limit */
      preview_limit: number;
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** SourceRun */
    SourceRun: {
      /** Expected Version */
      expected_version: number;
      overrides?: components["schemas"]["RunOverrides"];
    };
    /** SourceSchemas */
    SourceSchemas: {
      /** Items */
      items: {
        [key: string]: unknown;
      }[];
      /** Run Overrides Schema */
      run_overrides_schema: {
        [key: string]: unknown;
      };
      /** Schedule Schema */
      schedule_schema: {
        [key: string]: unknown;
      };
    } & {
      [key: string]: unknown;
    };
    /** SourceVersion */
    SourceVersion: {
      /** Expected Version */
      expected_version: number;
      /** Id */
      id: string;
    };
    /** Stats */
    Stats: {
      /** Applied */
      applied: number;
      /** By Source */
      by_source?:
        | {
            [key: string]: unknown;
          }[]
        | null;
      /** Funnel */
      funnel: {
        [key: string]: unknown;
      }[];
      /** Interview Rate */
      interview_rate?: number | null;
      /** Interviews */
      interviews: number;
      /** Median Days To Reply */
      median_days_to_reply?: number | null;
      /** Period */
      period: string;
      /** Replied */
      replied: number;
      /** Reply Rate */
      reply_rate?: number | null;
      /** Since */
      since?: string | null;
    } & {
      [key: string]: unknown;
    };
    /** Storage */
    Storage: {
      /** Database Bytes */
      database_bytes: number;
      /** Free Bytes */
      free_bytes: number;
      /** Kept Runs Per Source */
      kept_runs_per_source: number;
      /** Restore Limit Bytes */
      restore_limit_bytes: number;
      /** Restore Limit Configured Bytes */
      restore_limit_configured_bytes?: number | null;
      /** Retention Days */
      retention_days: number;
    } & {
      [key: string]: unknown;
    };
    /** Task */
    Task: {
      /** Attempts */
      attempts: number;
      /** Created At */
      created_at: string;
      /** Error */
      error?: string | null;
      /** Id */
      id: string;
      /** Job Id */
      job_id?: string | null;
      /** Job Title */
      job_title?: string | null;
      /** Kind */
      kind: string;
      /** Next Run At */
      next_run_at?: string | null;
      /**
       * Payload
       * @default {}
       */
      payload: {
        [key: string]: unknown;
      };
      /** Result */
      result?: {
        [key: string]: unknown;
      } | null;
      /** Run Id */
      run_id?: string | null;
      /** Source Id */
      source_id?: string | null;
      /** Source Name */
      source_name?: string | null;
      /** State */
      state: string;
      /** Updated At */
      updated_at: string;
    } & {
      [key: string]: unknown;
    };
    /** TaskPage */
    TaskPage: {
      /** Items */
      items: components["schemas"]["Task"][];
      /** Limit */
      limit?: number | null;
      /** Offset */
      offset?: number | null;
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** Template */
    Template: {
      /** Created At */
      created_at: string;
      /** File Count */
      file_count?: number | null;
      /** Guidance */
      guidance?: string | null;
      /** Id */
      id: string;
      /** Is Default */
      is_default: boolean;
      /** Kind */
      kind: string;
      /** Name */
      name: string;
      /** Rules */
      rules?: {
        [key: string]: unknown;
      } | null;
      /** Tex */
      tex?: string | null;
      /** Updated At */
      updated_at: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** TemplateCreate */
    TemplateCreate: {
      /**
       * Guidance
       * @default
       */
      guidance: string;
      /**
       * Idempotency Key
       * @description Retrying with the same key and request returns the record the first request created.
       */
      idempotency_key?: string | null;
      /**
       * Is Default
       * @default false
       */
      is_default: boolean;
      /**
       * Kind
       * @default cv
       * @enum {string}
       */
      kind: "cv" | "letter";
      /** Name */
      name: string;
      /**
       * Rules
       * @description Typed limits max_pages, max_bullets and max_bullet_chars; any other key (such as engine or date_format) is free-form. Writing rules belong in Preferences, not in a template.
       */
      rules?: {
        [key: string]: unknown;
      };
      /**
       * Tex
       * @default
       */
      tex: string;
    };
    /** TemplatePage */
    TemplatePage: {
      /** Items */
      items: components["schemas"]["Template"][];
      /** Limit */
      limit?: number | null;
      /** Offset */
      offset?: number | null;
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** TemplateUpdate */
    TemplateUpdate: {
      /** Expected Version */
      expected_version: number;
      /** Guidance */
      guidance?: string | null;
      /** Is Default */
      is_default?: boolean | null;
      /** Kind */
      kind?: ("cv" | "letter") | null;
      /** Name */
      name?: string | null;
      /**
       * Rules
       * @description Typed limits max_pages, max_bullets and max_bullet_chars; any other key (such as engine or date_format) is free-form. Writing rules belong in Preferences, not in a template.
       */
      rules?: {
        [key: string]: unknown;
      } | null;
      /** Tex */
      tex?: string | null;
    };
    /** Timeline */
    Timeline: {
      /** Counts */
      counts: {
        [key: string]: number;
      };
      /** Items */
      items: components["schemas"]["TimelineItem"][];
      /** Limit */
      limit?: number | null;
      /** Offset */
      offset?: number | null;
      /** Scope */
      scope: {
        [key: string]: unknown;
      };
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** TimelineItem */
    TimelineItem: {
      /** Actor */
      actor?: string | null;
      /** Application Id */
      application_id?: string | null;
      /** Batch Id */
      batch_id?: string | null;
      /** Created At */
      created_at: string;
      /** Event */
      event?: {
        [key: string]: unknown;
      } | null;
      /** Id */
      id: string;
      /** Job Id */
      job_id?: string | null;
      /**
       * Kind
       * @description note, event or reply
       */
      kind: string;
      /** Note */
      note?: {
        [key: string]: unknown;
      } | null;
      /** Scope */
      scope: {
        [key: string]: unknown;
      };
      /**
       * Type
       * @description note or event
       */
      type: string;
    } & {
      [key: string]: unknown;
    };
    /** Token */
    Token: {
      /** Created At */
      created_at: string;
      /** Id */
      id: string;
      /** Kind */
      kind: string;
      /** Name */
      name: string;
      /**
       * Token
       * @description The secret, shown only once.
       */
      token?: string | null;
    } & {
      [key: string]: unknown;
    };
    /** TokenInput */
    TokenInput: {
      /**
       * Idempotency Key
       * @description Retrying with the same key and request returns the token without its secret, which is shown only once.
       */
      idempotency_key?: string | null;
      /**
       * Kind
       * @description agent (the default) is scoped: it cannot change the owner password, manage tokens or restore a backup; owner has full access.
       * @default agent
       * @enum {string}
       */
      kind: "owner" | "agent";
      /** Name */
      name: string;
    };
    /** TokenList */
    TokenList: {
      /** Items */
      items: {
        [key: string]: unknown;
      }[];
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** TriageInput */
    TriageInput: {
      /** Expected Version */
      expected_version: number;
      /**
       * Reason
       * @description With dismissed: why, in a short sentence, shown in the Dismissed list (for example 'Junior role; I look for senior roles').
       */
      reason?: string | null;
      /**
       * Triage
       * @description new (to review), shortlisted (starts an application in stage Shortlisted when the job has no open one) or dismissed. Moving a shortlisted job back to new or dismissed removes the application its shortlist started while it is still empty; otherwise 409 application_has_work.
       * @enum {string}
       */
      triage: "new" | "shortlisted" | "dismissed";
    };
    /** UploadReservation */
    UploadReservation: {
      /**
       * Media Type
       * @default application/octet-stream
       */
      media_type: string;
      /** Name */
      name: string;
      /** Owner Id */
      owner_id: string;
      /**
       * Owner Type
       * @enum {string}
       */
      owner_type: "knowledge" | "template" | "document" | "job";
      /** Sha256 */
      sha256?: string | null;
      /** Size */
      size: number;
      /**
       * Source Sha256
       * @description For the PDF of a CV or letter revision that has a TeX source: the SHA-256 of that source (required then; a PDF naming another source is refused). A PDF-only revision names none.
       */
      source_sha256?: string | null;
    };
    /** Uploads */
    Uploads: {
      pdf?: components["schemas"]["FileGrant"] | null;
      source?: components["schemas"]["FileGrant"] | null;
    } & {
      [key: string]: unknown;
    };
    /** WorkspaceFile */
    WorkspaceFile: {
      /** Created At */
      created_at: string;
      /** Id */
      id: string;
      /** Media Type */
      media_type: string;
      /** Name */
      name: string;
      /** Owner Id */
      owner_id: string;
      /** Owner Type */
      owner_type: string;
      /** Sha256 */
      sha256: string;
      /** Size */
      size: number;
      /** Source Sha256 */
      source_sha256?: string | null;
      /** Url */
      url: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** WorkspaceInfo */
    WorkspaceInfo: {
      /**
       * Actor
       * @description owner, agent:<token name> or system: the label of changes.
       */
      actor: string;
      /** Api Base */
      api_base: string;
      /** Mcp Endpoint */
      mcp_endpoint: string;
      /** Name */
      name: string;
      /** Origin */
      origin?: string | null;
      /** Schema Version */
      schema_version: number;
      /** Single Owner */
      single_owner: boolean;
      storage: components["schemas"]["Storage"];
      /** Version */
      version: string;
      /** Workflow */
      workflow: string;
    } & {
      [key: string]: unknown;
    };
  };
  responses: never;
  parameters: never;
  requestBodies: never;
  headers: never;
  pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
  applications_list: {
    parameters: {
      query?: {
        /** @description Only applications recorded as applied at or after this time. */
        applied_since?: string | null;
        /** @description Only applications recorded as applied at or before this time; with stage=applied, the ones still waiting for a reply. */
        applied_until?: string | null;
        company?: string | null;
        job_id?: string | null;
        limit?: number;
        /** @description documents: Shortlisted applications missing a required document; reply_overdue: Applied applications without a reply for longer than the no-reply period, to close as no_response by hand. */
        needs?: ("documents" | "reply_overdue") | null;
        offset?: number;
        outcome?:
          ("accepted" | "rejected" | "not_pursued" | "no_response") | null;
        q?: string;
        sort?:
          | "updated"
          | "newest"
          | "oldest"
          | "company"
          | "stage"
          | "applied"
          | "deadline"
          | "priority";
        /** @description Only applications in this stage; ready is the Shortlisted ones that are Ready (every required document complete, no open blocking requirement). */
        stage?:
          | (
              | "shortlisted"
              | "ready"
              | "applied"
              | "interview"
              | "offer"
              | "closed"
            )
          | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ApplicationPage"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  applications_create: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ApplicationInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ApplicationChange"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  applications_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        application_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Application"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  applications_delete: {
    parameters: {
      query: {
        expected_version: number;
      };
      header?: never;
      path: {
        application_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Deleted"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  applications_update: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        application_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ApplicationPatch"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ApplicationChange"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  applications_history: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        application_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EventPage"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  timeline_get_1: {
    parameters: {
      query?: {
        job_id?: string | null;
        /** @description Only these kinds of entry: note, event (a recorded change) and reply (an employer reply recorded, corrected or removed). Every kind when omitted. */
        kinds?: ("note" | "event" | "reply")[] | null;
        limit?: number;
        offset?: number;
        /** @description Only the entries of the job itself (job) or of its applications (application). An application's timeline includes its job's entries unless scope=application. */
        scope?: ("job" | "application") | null;
        /** @description Only entries at or after this time. */
        since?: string | null;
        /** @description Only entries at or before this time (a date includes its day). */
        until?: string | null;
        /** @description Only entries by: owner (the dashboard or an owner token), agent (an agent token), system, unknown (recorded before 0.17, including application notes last written then). */
        who?: ("owner" | "agent" | "system" | "unknown")[] | null;
      };
      header?: never;
      path: {
        application_id: string | null;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Timeline"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  applications_bulk: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ApplicationBulk"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["BatchResult"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  login_api_v1_auth_login_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["PasswordInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  logout_api_v1_auth_logout_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
    };
  };
  owner_password_update: {
    parameters: {
      query?: {
        a?: unknown;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["PasswordInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PasswordChanged"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  session_api_v1_auth_session_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
    };
  };
  setup_api_v1_auth_setup_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["PasswordInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  backup_api_v1_backup_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
    };
  };
  workspace_backup: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["OperationGrant"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  restore_api_v1_backup_restore_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
    };
  };
  backups_list: {
    parameters: {
      query?: {
        a?: unknown;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["BackupList"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  backup_file_api_v1_backups__name__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        name: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  backups_delete: {
    parameters: {
      query?: {
        a?: unknown;
      };
      header?: never;
      path: {
        name: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Deleted"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  capabilities_api_v1_capabilities_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
    };
  };
  claims_list: {
    parameters: {
      query?: {
        approved?: boolean | null;
        knowledge_id?: string;
        limit?: number;
        offset?: number;
        q?: string;
        summary?: boolean;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ClaimPage"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  claims_create: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ClaimCreate"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Claim"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  claims_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        claim_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Claim"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  claims_delete: {
    parameters: {
      query: {
        expected_version: number;
      };
      header?: never;
      path: {
        claim_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Deleted"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  claims_update: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        claim_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ClaimUpdate"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Claim"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  career_import: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CareerImport"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ImportResult"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  career_preview_import: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ImportPreview"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ImportPreviewResult"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  knowledge_list: {
    parameters: {
      query?: {
        kind?: string;
        limit?: number;
        offset?: number;
        q?: string;
        summary?: boolean;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["KnowledgePage"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  knowledge_create: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["KnowledgeCreate"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Knowledge"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  knowledge_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        knowledge_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Knowledge"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  knowledge_delete: {
    parameters: {
      query: {
        expected_version: number;
      };
      header?: never;
      path: {
        knowledge_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Deleted"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  knowledge_update: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        knowledge_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["KnowledgeUpdate"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Knowledge"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  profile_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Profile"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  profile_update: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ProfileUpdate"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Profile"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  collection_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Collection"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  collection_update: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CollectionWrite"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Collection"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  collection_runs_list: {
    parameters: {
      query?: {
        limit?: number;
        offset?: number;
        source_id?: string | null;
        state?: string | null;
        summary?: boolean;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CollectionRunPage"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  collection_runs_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        run_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CollectionRun"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  collection_runs_cancel: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        run_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CollectionRun"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  documents_list: {
    parameters: {
      query?: {
        application_id?: string;
        kind?: string;
        limit?: number;
        offset?: number;
        q?: string;
        summary?: boolean;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DocumentPage"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  documents_create: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["DocumentCreate"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["NewDocument"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  documents_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        document_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Document"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  documents_delete: {
    parameters: {
      query: {
        expected_version: number;
      };
      header?: never;
      path: {
        document_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Deleted"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  documents_compare: {
    parameters: {
      query?: {
        other_id?: string;
      };
      header?: never;
      path: {
        document_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Comparison"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  events_list: {
    parameters: {
      query?: {
        /** @description Only changes by owner, agent (any agent token), agent:<token name>, system or unknown (before 0.17). */
        actor?: string | null;
        application_id?: string | null;
        /** @description Only the changes of one REST request or MCP tool call (b_...), or of one agent run before 0.24 (run:...). */
        batch_id?: string | null;
        /** @description Also list changes by the system (collection, worker, upgrade); they are left out unless actor=system. */
        include_system?: boolean;
        job_id?: string | null;
        kind?: string | null;
        limit?: number;
        offset?: number;
        since?: string | null;
        subject_id?: string | null;
        subject_type?: string | null;
        /** @description Changes to any of these kinds of record, for example document and file. */
        subject_types?: string[] | null;
        until?: string | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EventPage"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  examples_api_v1_examples_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
    };
  };
  example_file_api_v1_examples__name__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        name: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  export_api_v1_export_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
    };
  };
  workspace_export: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["OperationGrant"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  files_list: {
    parameters: {
      query?: {
        application_id?: string;
        limit?: number;
        media_type?: string;
        offset?: number;
        owner_id?: string;
        owner_type?: ("knowledge" | "template" | "document" | "job") | null;
        q?: string;
        summary?: boolean;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["FilePage"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  files_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        file_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["WorkspaceFile"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  files_delete: {
    parameters: {
      query: {
        expected_version: number;
      };
      header?: never;
      path: {
        file_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Deleted"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  file_content_api_v1_files__file_id__content_get: {
    parameters: {
      query?: {
        inline?: boolean;
      };
      header?: never;
      path: {
        file_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  files_reserve_download: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        file_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["FileGrant"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  files_reserve_upload: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["UploadReservation"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["FileGrant"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  jobs_list: {
    parameters: {
      query?: {
        /** @description Only jobs changed by one REST request or MCP tool call (its batch_id, as events_list and histories show it). Restore an agent's dismissals with jobs_bulk action inbox. */
        batch_id?: string | null;
        company?: string | null;
        complete?: boolean | null;
        created_since?: string | null;
        created_until?: string | null;
        /** @description Only dismissed jobs, by who dismissed them: agent (any agent token), agent:<token name>, owner (dashboard or owner token) or system (job sources, or before 0.21 without a record). */
        dismissed_by?: string | null;
        /** @description true: leave out jobs that require a language outside the owner's spoken_languages (settings); nothing is dismissed. With true or false the response's unspoken_required gives how many jobs of these filters require such a language. No effect while spoken_languages is empty. */
        hide_unspoken_required?: boolean | null;
        /** @description Also return counts: jobs by triage (new, shortlisted, dismissed, all) and dismissed jobs by who dismissed them, for the same search, company, location, source, date and signal filters. */
        include_counts?: boolean;
        /** @description Also return up to 200 distinct companies/locations/sources/job types matching the filters. */
        include_facets?: boolean;
        job_type?: string | null;
        limit?: number;
        location?: string | null;
        offset?: number;
        /** @description Only postings written in this language (ISO 639-1 code such as de, or a name such as German). */
        posting_language?: string | null;
        /** @description Only postings whose detected language is another one; postings of unknown language are left out. */
        posting_language_not?: string | null;
        q?: string;
        remote?: boolean | null;
        /** @description Only postings that state this language as required (alone or as one of alternatives). */
        requires?: string | null;
        /** @description Only jobs with this ingest signal: likely_duplicate (flagged as a copy of an earlier job), no_longer_listed (the board stopped listing it), language_required (the posting states a required language) or pending (signals not computed yet). */
        signal?:
          | (
              | "likely_duplicate"
              | "no_longer_listed"
              | "language_required"
              | "pending"
            )
          | null;
        /** @description Only jobs dismissed at or after this time. */
        since?: string | null;
        /** @description dismissed: most recently dismissed first. */
        sort?: "newest" | "oldest" | "company" | "title" | "dismissed";
        source?: string | null;
        /** @description new (to review), shortlisted (each has an application), dismissed, or active (not dismissed). */
        triage?: ("new" | "shortlisted" | "dismissed" | "active") | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["JobPage"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  jobs_create: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["JobInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Job"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description rate_limited */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  jobs_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        job_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Job"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  jobs_delete: {
    parameters: {
      query: {
        expected_version: number;
      };
      header?: never;
      path: {
        job_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Deleted"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  jobs_update: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        job_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["JobPatch"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["JobSummary"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  jobs_distinct: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        job_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["DistinctInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["JobSummary"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  jobs_merge: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        job_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["MergeInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Job"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  notes_list: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        job_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["NoteList"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  notes_create: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        job_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["NoteInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Note"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  timeline_get: {
    parameters: {
      query?: {
        application_id?: string | null;
        /** @description Only these kinds of entry: note, event (a recorded change) and reply (an employer reply recorded, corrected or removed). Every kind when omitted. */
        kinds?: ("note" | "event" | "reply")[] | null;
        limit?: number;
        offset?: number;
        /** @description Only the entries of the job itself (job) or of its applications (application). An application's timeline includes its job's entries unless scope=application. */
        scope?: ("job" | "application") | null;
        /** @description Only entries at or after this time. */
        since?: string | null;
        /** @description Only entries at or before this time (a date includes its day). */
        until?: string | null;
        /** @description Only entries by: owner (the dashboard or an owner token), agent (an agent token), system, unknown (recorded before 0.17, including application notes last written then). */
        who?: ("owner" | "agent" | "system" | "unknown")[] | null;
      };
      header?: never;
      path: {
        job_id: string | null;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Timeline"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  jobs_triage: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        job_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["TriageInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["JobSummary"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  jobs_bulk: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["JobBulk"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["BatchResult"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  jobs_duplicates: {
    parameters: {
      query?: {
        job_id?: string | null;
        limit?: number;
        match_location?: boolean;
        /** @description Lowest group confidence to return: 0.85 high tier only, 0.5 medium and high, 0 every candidate. */
        min_confidence?: number;
        offset?: number;
        triage?: ("new" | "shortlisted" | "dismissed") | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DuplicatePage"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  jobs_resolve: {
    parameters: {
      query?: {
        source_key?: string | null;
        url?: string;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ResolvedJobs"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  notes_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        note_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Note"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  notes_delete: {
    parameters: {
      query: {
        expected_version: number;
      };
      header?: never;
      path: {
        note_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Deleted"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  notes_update: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        note_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["NotePatch"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Note"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  notes_pin: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        note_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["NotePin"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Note"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  preferences_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Preferences"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  preferences_update: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        section:
          "looking_for" | "ruled_out" | "facts" | "writing" | "working_with_me";
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["PreferencesUpdate"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PreferenceSection"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  providers_list: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ProviderList"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  providers_update: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        provider_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ProviderPatch"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Provider"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  settings_update: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["SettingsUpdate"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Settings"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  skills_list: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SkillList"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  skills_get: {
    parameters: {
      query?: {
        path?: string;
      };
      header?: never;
      path: {
        name: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Skill"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  skill_file_api_v1_skills__name__files__path__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        name: string;
        path: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  sources_list: {
    parameters: {
      query?: {
        limit?: number;
        offset?: number;
        summary?: boolean;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SourcePage"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  sources_create: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["SourceCreate"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Source"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description rate_limited */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  sources_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        source_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Source"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  sources_delete: {
    parameters: {
      query: {
        expected_version: number;
      };
      header?: never;
      path: {
        source_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Deleted"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  sources_update: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        source_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["SourcePatch"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Source"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description rate_limited */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  sources_run: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        source_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["SourceRun"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Task"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description rate_limited */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  sources_bulk: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["SourceBulk"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["BatchResult"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description rate_limited */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  sources_preview: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["SourcePreview"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SourcePreviewResult"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description rate_limited */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  sources_schemas: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SourceSchemas"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  stats_get: {
    parameters: {
      query?: {
        /** @description Applications sent in the last 90 days (90d), the last 12 months (12m) or ever (all). */
        period?: "90d" | "12m" | "all";
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Stats"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  tasks_list: {
    parameters: {
      query?: {
        job_id?: string | null;
        kind?: string | null;
        limit?: number;
        offset?: number;
        source_id?: string | null;
        state?: string | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["TaskPage"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  tasks_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        task_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Task"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  tasks_cancel: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        task_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Task"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  tasks_retry: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        task_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Task"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description rate_limited */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  templates_list: {
    parameters: {
      query?: {
        kind?: string;
        limit?: number;
        offset?: number;
        q?: string;
        summary?: boolean;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["TemplatePage"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  templates_create: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["TemplateCreate"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Template"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  templates_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        template_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Template"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  templates_delete: {
    parameters: {
      query: {
        expected_version: number;
      };
      header?: never;
      path: {
        template_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Deleted"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  templates_update: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        template_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["TemplateUpdate"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Template"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  tokens_list: {
    parameters: {
      query?: {
        a?: unknown;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["TokenList"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  tokens_create: {
    parameters: {
      query?: {
        a?: unknown;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["TokenInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Token"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description request_size or file_size */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  tokens_revoke: {
    parameters: {
      query?: {
        a?: unknown;
      };
      header?: never;
      path: {
        token_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Deleted"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  download_api_v1_transfers_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
    };
  };
  upload_api_v1_transfers_put: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
    };
  };
  workspace_info: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["WorkspaceInfo"];
        };
      };
      /** @description unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
      /** @description validation */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
        };
      };
    };
  };
  health_health_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
    };
  };
}
