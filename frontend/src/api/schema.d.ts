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
     * Search application summaries with stage counts.
     * @description Each with ready, missing and last_reply. Filter by stage (ready: Shortlisted and Ready), needs (documents, reply_overdue), job_id, q, outcome, company, applied dates.
     */
    get: operations["applications_list"];
    put?: never;
    post?: never;
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
     * @description Read an application in full.
     */
    get: operations["applications_read"];
    put?: never;
    post?: never;
    /**
     * Delete an application permanently, only on the owner's explicit request.
     * @description With its documents and history; the job stays.
     */
    delete: operations["applications_delete"];
    options?: never;
    head?: never;
    /**
     * Update one application, with its version.
     * @description Stage, reply, outcome, priority, deadline, documents, requirements, answers.
     */
    patch: operations["applications_change"];
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
     * @description Notes and recorded changes, pinned notes first, then newest first.
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
  "/api/v1/applications/batch": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read up to 20 applications in full.
     * @description Job summary, required documents, ready and missing, requirements, questions, answers, replies, revisions and notes (the pinned one is the owner's guidance).
     */
    get: operations["applications_get"];
    put?: never;
    /**
     * Start applications for up to 50 jobs (stage Shortlisted; shortlists the job).
     * @description A job's open application is returned (created false) and takes the item's fields while Shortlisted. Never sends anything.
     */
    post: operations["applications_create"];
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Update up to 200 applications: stage, outcome, reply, fields.
     * @description A reply moves the stage. Set stage applied only when the owner says they applied. Other fields need expected_version. Each item has its own result.
     */
    patch: operations["applications_update"];
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
     * @description Up to 200 ids with versions, one result each.
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
    post: operations["auth_login"];
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
    post: operations["auth_logout"];
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
     * Change the owner password, giving the current one.
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
    get: operations["auth_session"];
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
    post: operations["auth_setup"];
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
    get: operations["backup_download"];
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
     * Reserve a backup download; take one before any permanent bulk clean-up.
     * @description A two-minute GET grant (curl line given). An agent's backup leaves out the password hash, session secret and tokens.
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
    post: operations["backup_restore"];
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
    get: operations["backups_download"];
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
    get: operations["capabilities_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/career/batch": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read up to 50 career entries in full, with highlights and files.
     * @description By ids, or the entries matching q and kind.
     */
    get: operations["career_get"];
    put?: never;
    /**
     * Add or update up to 50 career entries.
     * @description An item with career_id and expected_version updates; without, adds. Facts come from the owner, never from a job posting.
     */
    post: operations["career_save"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/career/entries": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Search career entries by q and kind; summary=false returns full records.
     * @description Search career entries by q and kind; summary=false returns full records.
     */
    get: operations["career_list"];
    put?: never;
    /**
     * Add a career entry.
     * @description Add a career entry.
     */
    post: operations["career_create"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/career/entries/{career_id}": {
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
     * Delete a career entry permanently, with its highlights and files.
     * @description Only on the owner's explicit request; document revisions are unchanged.
     */
    delete: operations["career_delete"];
    options?: never;
    head?: never;
    /**
     * Edit a career entry, with its version; dates=null clears the dates.
     * @description Edit a career entry, with its version; dates=null clears the dates.
     */
    patch: operations["career_update"];
    trace?: never;
  };
  "/api/v1/career/highlights": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Search highlights by entry (career_id), approval or text (q).
     * @description Search highlights by entry (career_id), approval or text (q).
     */
    get: operations["highlights_list"];
    put?: never;
    /**
     * Add a highlight; not approved by default.
     * @description Add a highlight; not approved by default.
     */
    post: operations["highlights_create"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/career/highlights/{highlight_id}": {
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
     * Delete a highlight permanently.
     * @description With its version; document revisions keep the ids they cite.
     */
    delete: operations["highlights_delete"];
    options?: never;
    head?: never;
    /**
     * Edit or approve a highlight, with its version.
     * @description Edit or approve a highlight, with its version.
     */
    patch: operations["highlights_update"];
    trace?: never;
  };
  "/api/v1/career/highlights/batch": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Add, update or approve up to 100 highlights.
     * @description Reusable wording on a career entry (career_id). highlight_id with expected_version updates. always_include puts it in every CV unless the job gives a reason not to.
     */
    post: operations["highlights_save"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
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
     * Import previewed career entries (owner only).
     * @description Appends the entries and, with the profile's version, applies the profile fields.
     *
     *     Owner only: an agent token is refused with 403 forbidden; not an MCP tool.
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
     * Preview a career import (owner only).
     * @description Parses JSON or plain text into entries and profile fields without storing anything.
     *
     *     Owner only: an agent token is refused with 403 forbidden; not an MCP tool.
     */
    post: operations["career_preview_import"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
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
     * Edit the profile, with its version.
     * @description Name, contact, headline, location, summary, links and metadata; omitted fields stay.
     */
    patch: operations["profile_update"];
    trace?: never;
  };
  "/api/v1/changes": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List recorded changes, newest first.
     * @description Each with actor (owner, agent:<name>, system), batch_id and subject. Filter by job_id, application_id, subject, actor, batch_id or dates.
     */
    get: operations["changes_list"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
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
     * Read the collection switch, its version, counts and failing sources.
     * @description include: kinds (source kinds and config fields), providers (limits, cooldowns), fetches (running, queued, failed).
     */
    get: operations["collection_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Turn scheduled collection on or off, change provider limits, stop or retry fetches.
     * @description With the collection's version; results has one result per provider, cancel, retry.
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
     * List collection runs by source or state.
     * @description List collection runs by source or state.
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
     * Stop a collection run; jobs already archived stay.
     * @description Stop a collection run; jobs already archived stay.
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
     * List document revisions by application and kind; q searches their text.
     * @description List document revisions by application and kind; q searches their text.
     */
    get: operations["documents_list"];
    put?: never;
    /**
     * Create a CV, letter or answers revision of an application.
     * @description CV/letter: pdf {name, size}, optional TeX source; PUT the PDF to uploads.pdf's absolute url (curl line given). Complete once its PDF is stored. Never sends.
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
     * Read a revision: complete, readable text, cited ids, note and files.
     * @description compare_to adds a line diff against that revision (previous for the one it replaces).
     */
    get: operations["documents_get"];
    put?: never;
    post?: never;
    /**
     * Delete a revision permanently, with its files; other revisions stay.
     * @description Delete a revision permanently, with its files; other revisions stay.
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
     * Compare two revisions line by line (by default with the one it replaces).
     * @description Compare two revisions line by line (by default with the one it replaces).
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
    get: operations["examples_list"];
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
    get: operations["examples_get"];
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
     * @description Download the workspace records as JSON, without file bytes or credentials (owner only).
     *
     *     Owner only: an agent token is refused with 403 forbidden; not an MCP tool.
     */
    get: operations["export_download"];
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
     * Reserve a records export (owner only).
     * @description A two-minute GET grant for the JSON records, without file bytes or credentials.
     *
     *     Owner only: an agent token is refused with 403 forbidden; not an MCP tool.
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
     * List file metadata by owner, name, media type or an application's revisions.
     * @description List file metadata by owner, name, media type or an application's revisions.
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
    get?: never;
    put?: never;
    post?: never;
    /**
     * Delete a career, template or job file (version 1).
     * @description A revision's files go with the revision (documents_delete).
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
    get: operations["files_content"];
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
     * Reserve a download of a file.
     * @description A short-lived GET grant: fetch its url with its headers (curl line given).
     */
    post: operations["files_download"];
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
     * Reserve an upload for a career, template, job or revision file.
     * @description Returns a one-shot grant: PUT the exact bytes to its absolute url with its headers (curl line given). sha256 is checked when given.
     */
    post: operations["files_upload"];
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
     * @description Filter by triage, q, url, signal, requires, posting_language, hide_unspoken_required, dismissed_by, dismissed_since, batch_id; include_counts adds totals. jobs_get has the posting.
     */
    get: operations["jobs_list"];
    put?: never;
    /**
     * Add a job from a URL, pasted text or fields.
     * @description A URL is read through the provider gate; needs_text means paste the posting with jobs_update. A known job is returned (created false).
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
     * @description Read a job in full.
     */
    get: operations["jobs_read"];
    put?: never;
    post?: never;
    /**
     * Delete a job permanently, only on the owner's explicit request.
     * @description With its applications, documents and files; collecting it again makes a new job.
     */
    delete: operations["jobs_delete"];
    options?: never;
    head?: never;
    /**
     * Correct a job's fields.
     * @description title, company, location, url, posting or metadata, with the job's version.
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
     * @description Mark a likely duplicate as a different vacancy.
     */
    post: operations["jobs_distinct"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/jobs/{job_id}/link": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Decide a likely duplicate.
     * @description same merges job_id into other_id (other_id survives, with postings, applications and notes); different clears the flag for good. Returns the job that remains.
     */
    post: operations["jobs_link"];
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
     * Merge a job into target_id, keeping postings, applications and notes.
     * @description Merge a job into target_id, keeping postings, applications and notes.
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
    get?: never;
    put?: never;
    /**
     * Add a note to a job, or to its application (application_id).
     * @description pinned lists it first and unpins the other; an application's pinned note is the owner's guidance for its documents.
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
     * @description Notes and recorded changes, pinned notes first, then newest first.
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
  "/api/v1/jobs/batch": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read up to 20 jobs in full.
     * @description Posting text, metadata, signals, dismissal, application and notes.
     */
    get: operations["jobs_get"];
    put?: never;
    post?: never;
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
     * @description Up to 200 ids with versions, one result each; forget is permanent.
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
     * @description Most confident first, with the signals that matched. min_confidence defaults to 0.5.
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
     * @description With triage and every application. Never ingests or fetches.
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
  "/api/v1/jobs/triage": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Triage up to 200 jobs: new, shortlisted or dismissed.
     * @description shortlisted starts the job's application; dismissed needs a reason the owner reads. Each item has its own result.
     */
    post: operations["jobs_triage"];
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
    get?: never;
    put?: never;
    post?: never;
    /**
     * Delete a note, with its version.
     * @description Delete a note, with its version.
     */
    delete: operations["notes_delete"];
    options?: never;
    head?: never;
    /**
     * Edit a note's body, pin or unpin it, with its version.
     * @description Edit a note's body, pin or unpin it, with its version.
     */
    patch: operations["notes_update"];
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
     * @description The five sections with their versions, no_reply_days and spoken_languages.
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
     * Replace one Preferences section's items, only when the owner asked.
     * @description looking_for, ruled_out, facts, writing (scope all, cv, letter) or working_with_me, with its version. Keep the owner's wording.
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
     * List providers with their HTTP limits and the shared window and cooldown.
     * @description List providers with their HTTP limits and the shared window and cooldown.
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
     * Edit a provider's HTTP policy, with its version.
     * @description Edit a provider's HTTP policy, with its version.
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
     * Change no_reply_days (1-365) or spoken_languages, with the settings' version.
     * @description spoken_languages are ISO 639-1 codes; jobs_list hide_unspoken_required uses them.
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
     * Read a skill, or without name the list of skills.
     * @description A skill is the method for one kind of work; path reads one of its files (or ../<skill>/<file>).
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
  "/api/v1/skills/{name}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read a skill, or without name the list of skills.
     * @description A skill is the method for one kind of work; path reads one of its files (or ../<skill>/<file>).
     */
    get: operations["skills_get_1"];
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
    get: operations["skills_file"];
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
     * List sources with schedule, last outcome and job counts.
     * @description Counts: found, shortlisted, applied, replied. sources_get has a source's recent checks.
     */
    get: operations["sources_list"];
    put?: never;
    /**
     * Save a source; paused by default.
     * @description Save a source; paused by default.
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
     * Read a source: its configuration, version and latest checks with their errors.
     * @description Read a source: its configuration, version and latest checks with their errors.
     */
    get: operations["sources_get"];
    put?: never;
    post?: never;
    /**
     * Delete a source permanently; archived jobs and their history stay.
     * @description Delete a source permanently; archived jobs and their history stay.
     */
    delete: operations["sources_delete"];
    options?: never;
    head?: never;
    /**
     * Edit or pause a source, with its version.
     * @description Edit or pause a source, with its version.
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
     * Run a source now, with its version and optional one-time overrides.
     * @description Run a source now, with its version and optional one-time overrides.
     */
    post: operations["sources_run_one"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/sources/batch": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Add or update up to 50 sources (saved searches, company boards, feeds).
     * @description source_id with expected_version updates; enabled false pauses. Preview a new source with sources_run first.
     */
    post: operations["sources_save"];
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
     * Enable, pause, run, configure or delete selected sources, one result each.
     * @description Enable, pause, run, configure or delete selected sources, one result each.
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
     * Preview a source without storing jobs, through the provider gate.
     * @description Preview a source without storing jobs, through the provider gate.
     */
    post: operations["sources_preview"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/sources/run": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Fetch a saved source now, or preview (preview true) what a source would collect.
     * @description Preview a saved source (source_id) or an unsaved one (url, kind, config); nothing is stored. Through the provider gate.
     */
    post: operations["sources_run"];
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
     * Describe the fields, schedules and run options of each source kind.
     * @description Describe the fields, schedules and run options of each source kind.
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
     * @description For applications sent in a period (90d, 12m, all): replies, interviews, rates, median days to a reply, the funnel.
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
     * Retry a failed or cancelled fetch with its frozen inputs.
     * @description Retry a failed or cancelled fetch with its frozen inputs.
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
     * List templates by kind or q; summary=false adds TeX, guidance and rules.
     * @description List templates by kind or q; summary=false adds TeX, guidance and rules.
     */
    get: operations["templates_list"];
    put?: never;
    /**
     * Add a template.
     * @description Add a template.
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
     * Read a template: TeX source, guidance, limits and its files.
     * @description Compile CV and letter from it on your machine.
     */
    get: operations["templates_get"];
    put?: never;
    post?: never;
    /**
     * Delete a template permanently, with its files.
     * @description Only on the owner's explicit request; document revisions are unchanged.
     */
    delete: operations["templates_delete"];
    options?: never;
    head?: never;
    /**
     * Edit a template, with its version.
     * @description Edit a template, with its version.
     */
    patch: operations["templates_update"];
    trace?: never;
  };
  "/api/v1/templates/save": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Add a template, or update one (template_id, expected_version).
     * @description TeX source, guidance, limits (rules) and is_default; the first of a kind is the default.
     */
    post: operations["templates_save"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
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
     * @description Including the token making the request; an unknown id is 404.
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
    get: operations["transfers_download"];
    /**
     * Upload
     * @description Upload raw file bytes with a grant.
     *
     *     The second step of files_upload or of a revision's uploads: PUT the exact bytes to
     *     the grant's url with its headers (X-Transfer-Token). Returns the file.
     */
    put: operations["transfers_upload"];
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
     * @description Version, schema, this token's actor label, storage and the workflow.
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
  "/api/v1/workspace/context": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Start here: what to know before deciding or writing.
     * @description Counts, settings, profile, Preferences, career summary, templates, skills and feedback (the owner's corrections of agent work since your last read).
     */
    get: operations["workspace_context"];
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
    get: operations["health"];
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
      questions: components["schemas"]["FormQuestion"][];
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
      requirements: components["schemas"]["EmployerRequirement"][];
      /** Stage */
      stage: string;
      /** Updated At */
      updated_at: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** ApplicationBatch */
    ApplicationBatch: {
      /** Items */
      items: components["schemas"]["Application"][];
      /**
       * Missing
       * @description Requested ids that do not exist.
       * @default []
       */
      missing: string[];
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
      /**
       * Outcome
       * @description With close: how it ended.
       */
      outcome?:
        ("accepted" | "rejected" | "not_pursued" | "no_response") | null;
      /**
       * Stage
       * @description With reopen: the stage to return to.
       */
      stage?: ("shortlisted" | "applied" | "interview" | "offer") | null;
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
      questions: components["schemas"]["FormQuestion"][];
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
      requirements: components["schemas"]["EmployerRequirement"][];
      /** Stage */
      stage: string;
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
       * @description What Ready needs (default cv and letter).
       * @default [
       *       "cv",
       *       "letter"
       *     ]
       */
      required_documents: ("cv" | "letter")[];
      /** Requirements */
      requirements?: components["schemas"]["Requirement"][];
    };
    /** ApplicationItem */
    ApplicationItem: {
      /** Answers */
      answers?: {
        [key: string]: unknown;
      } | null;
      /** Application Id */
      application_id: string;
      /**
       * Applied On
       * @description With applied: the day it was sent; today when omitted.
       */
      applied_on?: string | null;
      /** Concluded On */
      concluded_on?: string | null;
      /** Deadline */
      deadline?: string | null;
      /**
       * Expected Version
       * @description The version read; required to change priority, deadline, documents, requirements, questions or answers.
       */
      expected_version?: number | null;
      /** Outcome */
      outcome?:
        ("accepted" | "rejected" | "not_pursued" | "no_response") | null;
      /** Priority */
      priority?: number | null;
      /** Questions */
      questions?: components["schemas"]["Question"][] | null;
      /** @description An employer reply: interview, offer and rejection move the stage; other never does. */
      reply?: components["schemas"]["NewReply"] | null;
      /** @description Correct or delete a recorded reply. */
      reply_fix?: components["schemas"]["ReplyFix"] | null;
      /** Required Documents */
      required_documents?: ("cv" | "letter")[] | null;
      /**
       * Requirements
       * @description Replaces the list; keep ids to keep items.
       */
      requirements?: components["schemas"]["Requirement"][] | null;
      /**
       * Stage
       * @description applied only when the owner says they applied; closed needs outcome.
       */
      stage?:
        ("shortlisted" | "applied" | "interview" | "offer" | "closed") | null;
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
    /**
     * ApplicationPatch
     * @description A change of one application, with its version.
     */
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
       * @description What Ready needs (default cv and letter).
       */
      required_documents?: ("cv" | "letter")[] | null;
      /**
       * Requirements
       * @description Replaces the whole requirement list; include existing ids to keep them.
       */
      requirements?: components["schemas"]["Requirement"][] | null;
      /**
       * Stage
       * @description applied is Mark applied (applied_at defaults to now); shortlisted again undoes it while the application has no reply, clearing applied_at. Record an employer reply with reply, which sets the stage itself.
       */
      stage?:
        ("shortlisted" | "applied" | "interview" | "offer" | "closed") | null;
    };
    /** ApplicationRef */
    ApplicationRef: {
      /** Id */
      id: string;
      /** Outcome */
      outcome?: string | null;
      /** Stage */
      stage: string;
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
      /** Stage */
      stage: string;
      /** Updated At */
      updated_at: string;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** ApplicationsCreate */
    ApplicationsCreate: {
      /** Items */
      items: components["schemas"]["ApplicationInput"][];
    };
    /** ApplicationsUpdate */
    ApplicationsUpdate: {
      /** Items */
      items: components["schemas"]["ApplicationItem"][];
    };
    /** BackupAttempt */
    BackupAttempt: {
      /** Attempted At */
      attempted_at: string;
      /** Error */
      error?: string | null;
      /**
       * Outcome
       * @description ok, failed or skipped.
       */
      outcome: string;
    } & {
      [key: string]: unknown;
    };
    /** BackupList */
    BackupList: {
      /** Items */
      items: components["schemas"]["KeptBackup"][];
      schedule: components["schemas"]["BackupSchedule"];
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** BackupSchedule */
    BackupSchedule: {
      /** Age Hours */
      age_hours?: number | null;
      /** Enabled */
      enabled: boolean;
      /** Interval Hours */
      interval_hours: number;
      /** Keep */
      keep: number;
      /** Last At */
      last_at?: string | null;
      last_attempt?: components["schemas"]["BackupAttempt"] | null;
      /** Ok */
      ok: boolean;
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
      /**
       * Id
       * @description The record; none for a failed create.
       */
      id?: string | null;
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
       * @description The batch of the recorded changes (changes_list batch_id).
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
    /** CareerBatch */
    CareerBatch: {
      /**
       * Items
       * @description Full entries with highlights and files.
       */
      items: components["schemas"]["CareerEntry"][];
      /**
       * Missing
       * @default []
       */
      missing: string[];
    } & {
      [key: string]: unknown;
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
    /** CareerEntry */
    CareerEntry: {
      /** Created At */
      created_at: string;
      /** Dates */
      dates?: {
        [key: string]: unknown;
      } | null;
      /** File Count */
      file_count?: number | null;
      /** Highlight Count */
      highlight_count?: number | null;
      /** Highlight Preview */
      highlight_preview?: string | null;
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
    /** CareerImport */
    CareerImport: {
      /** Entries */
      entries?: components["schemas"]["EntryCreate"][];
      /** Expected Profile Version */
      expected_profile_version?: number | null;
      /** Profile */
      profile?: {
        [key: string]: unknown;
      } | null;
    };
    /** CareerItem */
    CareerItem: {
      /**
       * Career Id
       * @description Update this entry; omit to add one.
       */
      career_id?: string | null;
      dates?: components["schemas"]["CareerDates"] | null;
      /**
       * Expected Version
       * @description Required to update.
       */
      expected_version?: number | null;
      /** Idempotency Key */
      idempotency_key?: string | null;
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
    /** CareerPage */
    CareerPage: {
      /** Items */
      items: components["schemas"]["CareerEntry"][];
      /** Limit */
      limit?: number | null;
      /** Offset */
      offset?: number | null;
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** CareerSave */
    CareerSave: {
      /** Items */
      items: components["schemas"]["CareerItem"][];
    };
    /** Collection */
    Collection: {
      /** Enabled */
      enabled: boolean;
      /** Enabled Sources */
      enabled_sources: number;
      /** Fetches */
      fetches?: {
        [key: string]: unknown;
      } | null;
      /** Kinds */
      kinds?: {
        [key: string]: unknown;
      } | null;
      /** Next Run At */
      next_run_at?: string | null;
      /** Providers */
      providers?:
        | {
            [key: string]: unknown;
          }[]
        | null;
      /** Queued Tasks */
      queued_tasks: number;
      /** @description collection_update: one result per provider, cancel, retry. */
      results?: components["schemas"]["BatchResult"] | null;
      /** Running Tasks */
      running_tasks: number;
      /** Source Count */
      source_count: number;
      /** Sources Failing */
      sources_failing?: number | null;
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
      tasks: components["schemas"]["RunTask"][];
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
    /**
     * CollectionWrite
     * @description The collection switch with its version; also provider limits and fetches to stop
     *     or retry (each applied on its own, results in ``results``).
     */
    CollectionWrite: {
      /**
       * Cancel
       * @description Fetch (task) or run ids to stop.
       */
      cancel?: string[];
      /**
       * Enabled
       * @description Scheduled collection on or off.
       */
      enabled?: boolean | null;
      /**
       * Expected Version
       * @description The collection's version.
       */
      expected_version: number;
      /**
       * Providers
       * @description Provider limits, each with its own expected_version.
       */
      providers?: components["schemas"]["ProviderChange"][];
      /**
       * Retry
       * @description Failed or cancelled fetch ids.
       */
      retry?: string[];
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
       * Career Ids
       * @default []
       */
      career_ids: string[];
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
      /**
       * Highlight Ids
       * @default []
       */
      highlight_ids: string[];
      /** Id */
      id: string;
      /** Kind */
      kind: string;
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
       * Career Ids
       * @description Career entries the revision uses.
       */
      career_ids?: string[];
      /**
       * Content
       * @description answers or other: structured content. Not for cv or letter.
       */
      content?: {
        [key: string]: unknown;
      } | null;
      /**
       * Highlight Ids
       * @description Approved highlights the revision uses.
       */
      highlight_ids?: string[];
      /**
       * Idempotency Key
       * @description A retry with the same key returns the first revision.
       */
      idempotency_key?: string | null;
      /**
       * Kind
       * @default cv
       * @enum {string}
       */
      kind: "cv" | "letter" | "answers" | "other";
      /**
       * Note
       * @default
       */
      note: string;
      /** @description cv or letter, required: the PDF to PUT with uploads.pdf; complete and immutable once stored. */
      pdf?: components["schemas"]["FileSpec"] | null;
      /**
       * Previous Id
       * @description The revision this one replaces.
       */
      previous_id?: string | null;
      /**
       * Source
       * @description cv or letter, optional: the TeX source inline (at most 256 KB); the PDF must be built from it.
       */
      source?: string | null;
      /** @description Instead of source: a .tex file (name, size, sha256) to PUT with uploads.source, before the PDF. */
      source_file?: components["schemas"]["FileSpec"] | null;
      /**
       * Title
       * @default
       */
      title: string;
    };
    /** DocumentDetail */
    DocumentDetail: {
      /** Application Id */
      application_id: string;
      /**
       * Career Ids
       * @default []
       */
      career_ids: string[];
      /** @description With compare_to: the line diff against that revision. */
      comparison?: components["schemas"]["Comparison"] | null;
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
      /**
       * Highlight Ids
       * @default []
       */
      highlight_ids: string[];
      /** Id */
      id: string;
      /** Kind */
      kind: string;
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
    /** EmployerRequirement */
    EmployerRequirement: {
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
    /** EntryCreate */
    EntryCreate: {
      dates?: components["schemas"]["CareerDates"] | null;
      /**
       * Idempotency Key
       * @description A retry with the same key returns the first result.
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
    /** EntryUpdate */
    EntryUpdate: {
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
    /**
     * Error
     * @description Every error response. Codes by status: 401 unauthorized: sign in or send a valid bearer token (also transfer_token, transfer_expired, transfer_used: a grant works once). 403 forbidden: an agent token on an owner-only operation; csrf: a browser write without its X-CSRF-Token header. 404 not_found: the record or route does not exist, including a record the body names (application_id, career_id...). 409 conflict: the record changed (details.current_version and details.id); also constraint, application_has_work and similar rule conflicts. 413 request_size or file_size: the body or file is over its limit. 422 validation: details lists {field, message, type} per invalid field; other codes name a rule. 429 rate_limited: the shared provider gate is waiting; details.retry_after_seconds and the Retry-After header give the wait.
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
       * @description Structured details: field errors for validation, current_version and id for a version conflict.
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
      /**
       * Curl
       * @description The same request as a shell line.
       */
      curl?: string | null;
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
      /**
       * Url
       * @description Absolute, on the workspace's public origin.
       */
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
    /**
     * FormQuestion
     * @description A question of the employer's application form.
     */
    FormQuestion: {
      /** Id */
      id: string;
      /** Label */
      label: string;
      /** Max Length */
      max_length?: number | null;
      /**
       * Options
       * @default []
       */
      options: string[];
      /**
       * Required
       * @default false
       */
      required: boolean;
      /**
       * Type
       * @default text
       */
      type: string;
    } & {
      [key: string]: unknown;
    };
    /** Highlight */
    Highlight: {
      /** Always Include */
      always_include: boolean;
      /** Approved */
      approved: boolean;
      /** Career Id */
      career_id: string;
      /** Career Organization */
      career_organization?: string | null;
      /** Career Title */
      career_title?: string | null;
      /** Created At */
      created_at: string;
      /** Id */
      id: string;
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
    /** HighlightCreate */
    HighlightCreate: {
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
       * Career Id
       * @description The career entry it belongs to.
       */
      career_id: string;
      /**
       * Idempotency Key
       * @description A retry with the same key returns the first result.
       */
      idempotency_key?: string | null;
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
    /** HighlightItem */
    HighlightItem: {
      /**
       * Always Include
       * @description In every CV unless the job gives a reason to leave it out.
       */
      always_include?: boolean | null;
      /** Approved */
      approved?: boolean | null;
      /**
       * Career Id
       * @description Its entry; required to add one.
       */
      career_id?: string | null;
      /**
       * Expected Version
       * @description Required to update.
       */
      expected_version?: number | null;
      /**
       * Highlight Id
       * @description Update this one; omit to add one.
       */
      highlight_id?: string | null;
      /** Idempotency Key */
      idempotency_key?: string | null;
      /** Metadata */
      metadata?: {
        [key: string]: unknown;
      } | null;
      /** Position */
      position?: number | null;
      /** Text */
      text?: string | null;
    };
    /** HighlightPage */
    HighlightPage: {
      /** Items */
      items: components["schemas"]["Highlight"][];
      /** Limit */
      limit?: number | null;
      /** Offset */
      offset?: number | null;
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** HighlightsSave */
    HighlightsSave: {
      /** Items */
      items: components["schemas"]["HighlightItem"][];
    };
    /** HighlightUpdate */
    HighlightUpdate: {
      /** Always Include */
      always_include?: boolean | null;
      /** Approved */
      approved?: boolean | null;
      /** Career Id */
      career_id?: string | null;
      /** Expected Version */
      expected_version: number;
      /** Metadata */
      metadata?: {
        [key: string]: unknown;
      } | null;
      /** Position */
      position?: number | null;
      /** Text */
      text?: string | null;
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
      /** Entries */
      entries: {
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
      items: components["schemas"]["CareerEntry"][];
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
       * Needs Text
       * @description On jobs_create: the posting text could not be read; add it with jobs_update.
       */
      needs_text?: boolean | null;
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
    /** JobBatch */
    JobBatch: {
      /** Items */
      items: components["schemas"]["Job"][];
      /**
       * Missing
       * @description Requested ids that do not exist.
       * @default []
       */
      missing: string[];
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
       * @description A retry with the same key returns the first result.
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
    /** JobTriage */
    JobTriage: {
      /** Items */
      items: components["schemas"]["TriageItem"][];
    };
    /** KeptBackup */
    KeptBackup: {
      /** Created At */
      created_at: string;
      /**
       * Kind
       * @description scheduled or pre_upgrade.
       */
      kind: string;
      /** Name */
      name: string;
      /** Size Bytes */
      size_bytes: number;
    } & {
      [key: string]: unknown;
    };
    /** LinkInput */
    LinkInput: {
      /**
       * Decision
       * @description same merges job_id into other_id (other_id survives); different clears the flag.
       * @enum {string}
       */
      decision: "same" | "different";
      /**
       * Expected Version
       * @description Required with same: job_id's version.
       */
      expected_version?: number | null;
      /**
       * Other Id
       * @description The job flagged as its likely duplicate.
       */
      other_id: string;
      /**
       * Other Version
       * @description With same, optional: other_id's version.
       */
      other_version?: number | null;
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
       * Career Ids
       * @default []
       */
      career_ids: string[];
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
      /**
       * Highlight Ids
       * @default []
       */
      highlight_ids: string[];
      /** Id */
      id: string;
      /** Kind */
      kind: string;
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
    /** NewReply */
    NewReply: {
      /**
       * Date
       * @description YYYY-MM-DD; today when omitted.
       */
      date?: string | null;
      /**
       * Kind
       * @enum {string}
       */
      kind: "interview" | "rejection" | "offer" | "other";
      /** Note */
      note?: string | null;
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
       * @description Put the note on this application of the job.
       */
      application_id?: string | null;
      /** Body */
      body: string;
      /**
       * Idempotency Key
       * @description A retry with the same key returns the first note.
       */
      idempotency_key?: string | null;
      /**
       * Pinned
       * @default false
       */
      pinned: boolean;
    };
    /** NotePatch */
    NotePatch: {
      /** Body */
      body?: string | null;
      /** Expected Version */
      expected_version: number;
      /**
       * Pinned
       * @description true pins it (unpinning the other note of its job or application); false unpins it.
       */
      pinned?: boolean | null;
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
      /**
       * Curl
       * @description The same request as a shell line.
       */
      curl?: string | null;
      /** Expires In */
      expires_in: number;
      /** Headers */
      headers: {
        [key: string]: string;
      };
      /** Method */
      method: string;
      /**
       * Url
       * @description Absolute, on the workspace's public origin.
       */
      url: string;
    } & {
      [key: string]: unknown;
    };
    /** PasswordChange */
    PasswordChange: {
      /** Current Password */
      current_password: string;
      /** Password */
      password: string;
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
       * @description writing only: all, cv or letter; all when omitted.
       */
      scope?: ("all" | "cv" | "letter") | null;
      /**
       * Text
       * @description In the owner's words.
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
       * @description The whole section, in order (each at most 2000 characters).
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
      capability: components["schemas"]["ProviderCapability"];
      /** Id */
      id: string;
      /** Name */
      name: string;
      policy: components["schemas"]["ProviderPolicy"];
      runtime: components["schemas"]["ProviderRuntime"];
      /** Updated At */
      updated_at?: string | null;
      /** Version */
      version: number;
    } & {
      [key: string]: unknown;
    };
    /** ProviderCapability */
    ProviderCapability: {
      /** Credentials Required */
      credentials_required: boolean;
      /** Description */
      description: string;
      /** Kind */
      kind: string;
      /** Supported */
      supported: boolean;
      /** Transport Version */
      transport_version: string;
    } & {
      [key: string]: unknown;
    };
    /** ProviderChange */
    ProviderChange: {
      /**
       * Clear Cooldown
       * @description true lifts a pause the provider asked for (Retry-After) now.
       * @default false
       */
      clear_cooldown: boolean;
      /** Enabled */
      enabled?: boolean | null;
      /** Expected Version */
      expected_version: number;
      /** Min Interval Seconds */
      min_interval_seconds?: number | null;
      /** Provider Id */
      provider_id: string;
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
    /** ProviderPolicy */
    ProviderPolicy: {
      /** Enabled */
      enabled: boolean;
      /**
       * Min Interval Seconds
       * @description Seconds between two requests.
       */
      min_interval_seconds: number;
    } & {
      [key: string]: unknown;
    };
    /**
     * ProviderRuntime
     * @description The shared window: when the next request may go and what the last one answered.
     */
    ProviderRuntime: {
      /** Cooldown Until */
      cooldown_until?: string | null;
      /** Last Error */
      last_error?: string | null;
      /** Last Request At */
      last_request_at?: string | null;
      /** Last Status */
      last_status?: number | null;
      /** Next Allowed At */
      next_allowed_at?: string | null;
      /** Requests Day */
      requests_day: number;
      /** Requests Hour */
      requests_hour: number;
      /** Total Requests */
      total_requests: number;
    } & {
      [key: string]: unknown;
    };
    /** ProviderUpdate */
    ProviderUpdate: {
      /**
       * Clear Cooldown
       * @description true lifts a pause the provider asked for (Retry-After) now.
       * @default false
       */
      clear_cooldown: boolean;
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
    /** ReplyFix */
    ReplyFix: {
      /** Date */
      date?: string | null;
      /**
       * Delete
       * @default false
       */
      delete: boolean;
      /** Kind */
      kind?: ("interview" | "rejection" | "offer" | "other") | null;
      /** Note */
      note?: string | null;
      /** Reply Id */
      reply_id: string;
    };
    /**
     * Requirement
     * @description An employer requirement from the posting or the form.
     */
    Requirement: {
      /**
       * Blocking
       * @description Blocks Ready until resolved.
       * @default false
       */
      blocking: boolean;
      /**
       * Id
       * @description Assigned when omitted.
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
       * @description Resolution or open question.
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
    /**
     * RunTask
     * @description One fetch of a run, without its inputs and result.
     */
    RunTask: {
      /** Attempts */
      attempts: number;
      /** Error */
      error?: string | null;
      /** Id */
      id: string;
      /** Kind */
      kind: string;
      /** Next Run At */
      next_run_at?: string | null;
      /** Provider */
      provider?: string | null;
      /** State */
      state: string;
      /** Updated At */
      updated_at: string;
    } & {
      [key: string]: unknown;
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
       * @description The settings' version (0 before the first save).
       */
      expected_version: number;
      /**
       * No Reply Days
       * @description Days without an answer after which an application is overdue.
       */
      no_reply_days?: number | null;
      /**
       * Spoken Languages
       * @description ISO 639-1 codes such as en or de.
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
       * @description A retry with the same key returns the first result.
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
    /** SourceDetail */
    SourceDetail: {
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
      /**
       * Recent Runs
       * @description The latest checks, newest first.
       * @default []
       */
      recent_runs: {
        [key: string]: unknown;
      }[];
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
    /**
     * SourceItem
     * @description A source to create (no source_id) or update (source_id and expected_version).
     */
    SourceItem: {
      /** Config */
      config?: {
        [key: string]: unknown;
      } | null;
      /**
       * Enabled
       * @description false pauses it.
       */
      enabled?: boolean | null;
      /**
       * Expected Version
       * @description Required to update.
       */
      expected_version?: number | null;
      filters?: components["schemas"]["Filters"] | null;
      /** Idempotency Key */
      idempotency_key?: string | null;
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
      /**
       * Source Id
       * @description Update this source; omit to add.
       */
      source_id?: string | null;
      /** Url */
      url?: string | null;
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
    /**
     * SourceRunInput
     * @description Fetch a saved source now, or preview a saved or unsaved one without storing jobs.
     */
    SourceRunInput: {
      /** Config */
      config?: {
        [key: string]: unknown;
      } | null;
      /**
       * Expected Version
       * @description Required to fetch a saved source.
       */
      expected_version?: number | null;
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
      overrides?: components["schemas"]["RunOverrides"] | null;
      /**
       * Preview
       * @description true: up to 20 postings it would collect, nothing stored.
       * @default false
       */
      preview: boolean;
      /**
       * Source Id
       * @description The saved source.
       */
      source_id?: string | null;
      /** Url */
      url?: string | null;
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
    /** SourcesSave */
    SourcesSave: {
      /** Items */
      items: components["schemas"]["SourceItem"][];
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
    /** Template */
    Template: {
      /** Created At */
      created_at: string;
      /** File Count */
      file_count?: number | null;
      /**
       * Files
       * @default []
       */
      files: components["schemas"]["WorkspaceFile"][];
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
       * @description A retry with the same key returns the first result.
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
    /** TemplateSave */
    TemplateSave: {
      /**
       * Expected Version
       * @description Required to update.
       */
      expected_version?: number | null;
      /** Guidance */
      guidance?: string | null;
      /** Idempotency Key */
      idempotency_key?: string | null;
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
      /**
       * Template Id
       * @description Update this one; omit to add one.
       */
      template_id?: string | null;
      /** Tex */
      tex?: string | null;
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
      items: components["schemas"]["TokenRow"][];
      /** Total */
      total: number;
    } & {
      [key: string]: unknown;
    };
    /** TokenRow */
    TokenRow: {
      /** Created At */
      created_at: string;
      /** Id */
      id: string;
      /** Kind */
      kind: string;
      /** Last Used At */
      last_used_at?: string | null;
      /** Name */
      name: string;
    } & {
      [key: string]: unknown;
    };
    /** TriageItem */
    TriageItem: {
      /** Job Id */
      job_id: string;
      /**
       * Reason
       * @description Required with dismissed: one sentence the owner reads.
       */
      reason?: string | null;
      /**
       * To
       * @description new, shortlisted (starts its application) or dismissed.
       * @enum {string}
       */
      to: "new" | "shortlisted" | "dismissed";
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
      owner_type: "career" | "template" | "document" | "job";
      /** Sha256 */
      sha256?: string | null;
      /** Size */
      size: number;
      /**
       * Source Sha256
       * @description A revision's PDF built from a TeX source: that source's SHA-256 (required then).
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
    /**
     * WorkspaceContext
     * @description workspace_context: what to know before deciding or writing.
     */
    WorkspaceContext: {
      /** Career */
      career: {
        [key: string]: unknown;
      }[];
      /** Counts */
      counts: {
        [key: string]: number;
      };
      /**
       * Feedback
       * @description The owner's corrections of agent work since the previous read.
       * @default []
       */
      feedback: {
        [key: string]: unknown;
      }[];
      /** Preferences */
      preferences: {
        [key: string]: unknown;
      };
      /** Profile */
      profile: {
        [key: string]: unknown;
      };
      /** Settings */
      settings: {
        [key: string]: unknown;
      };
      /** Skills */
      skills: {
        [key: string]: unknown;
      }[];
      /** Templates */
      templates: {
        [key: string]: unknown;
      }[];
      /** Workspace */
      workspace: {
        [key: string]: unknown;
      };
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
        /** @description Applied at or after this time. */
        applied_since?: string | null;
        /** @description Applied at or before this time. */
        applied_until?: string | null;
        company?: string | null;
        job_id?: string | null;
        limit?: number;
        /** @description documents: Shortlisted, missing a document; reply_overdue: Applied, no reply past no_reply_days. */
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
        /** @description ready: Shortlisted with every required document complete and nothing blocking. */
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
  applications_read: {
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
  applications_change: {
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
  timeline_get_1: {
    parameters: {
      query?: {
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
  applications_get: {
    parameters: {
      query: {
        /** @description Up to 20 application ids. */
        ids: string[];
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
          "application/json": components["schemas"]["ApplicationBatch"];
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
        "application/json": components["schemas"]["ApplicationsCreate"];
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
  applications_update: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ApplicationsUpdate"];
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
  auth_login: {
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
  auth_logout: {
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
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["PasswordChange"];
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
  auth_session: {
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
  auth_setup: {
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
  backup_download: {
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
  backup_restore: {
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
  backups_download: {
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
  capabilities_get: {
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
  career_get: {
    parameters: {
      query?: {
        /** @description Up to 50 entry ids; omit to search q and kind. */
        ids?: string[] | null;
        kind?: string;
        q?: string;
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
          "application/json": components["schemas"]["CareerBatch"];
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
  career_save: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CareerSave"];
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
  career_list: {
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
          "application/json": components["schemas"]["CareerPage"];
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
  career_create: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["EntryCreate"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CareerEntry"];
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
  career_delete: {
    parameters: {
      query: {
        expected_version: number;
      };
      header?: never;
      path: {
        career_id: string;
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
  career_update: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        career_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["EntryUpdate"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CareerEntry"];
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
  highlights_list: {
    parameters: {
      query?: {
        approved?: boolean | null;
        career_id?: string;
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
          "application/json": components["schemas"]["HighlightPage"];
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
  highlights_create: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["HighlightCreate"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Highlight"];
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
  highlights_delete: {
    parameters: {
      query: {
        expected_version: number;
      };
      header?: never;
      path: {
        highlight_id: string;
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
  highlights_update: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        highlight_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["HighlightUpdate"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Highlight"];
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
  highlights_save: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["HighlightsSave"];
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
  changes_list: {
    parameters: {
      query?: {
        /** @description owner, agent, agent:<token name>, system or unknown. */
        actor?: string | null;
        application_id?: string | null;
        /** @description The changes of one call (b_...) or of an agent run before 0.24 (run:...). */
        batch_id?: string | null;
        /** @description Also the system's changes (left out unless actor=system). */
        include_system?: boolean;
        job_id?: string | null;
        kind?: string | null;
        limit?: number;
        offset?: number;
        since?: string | null;
        subject_id?: string | null;
        subject_type?: string | null;
        /** @description Changes to these kinds of record, such as document and file. */
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
  collection_get: {
    parameters: {
      query?: {
        /** @description kinds: source kinds and their config fields; providers: limits and cooldowns; fetches: active and failed fetches. */
        include?: ("kinds" | "providers" | "fetches")[];
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
  documents_get: {
    parameters: {
      query?: {
        compare_to?: string;
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
          "application/json": components["schemas"]["DocumentDetail"];
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
  examples_list: {
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
  examples_get: {
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
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
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
  export_download: {
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
        owner_type?: ("career" | "template" | "document" | "job") | null;
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
  files_content: {
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
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
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
  files_download: {
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
  files_upload: {
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
  jobs_list: {
    parameters: {
      query?: {
        /** @description Jobs changed by one call (its batch_id in changes_list). */
        batch_id?: string | null;
        /** @description Exactly this company name. */
        company?: string | null;
        /** @description true: the posting text is complete; false: it still needs text (needs_text). */
        complete?: boolean | null;
        /** @description Added at or after this time. */
        created_since?: string | null;
        /** @description Added at or before this time. */
        created_until?: string | null;
        /** @description Dismissed by owner, agent, agent:<token name> or system. */
        dismissed_by?: string | null;
        /** @description Dismissed at or after this time. */
        dismissed_since?: string | null;
        /** @description true hides jobs requiring a language outside spoken_languages; unspoken_required counts them. */
        hide_unspoken_required?: boolean | null;
        /** @description Also totals by triage and by who dismissed. */
        include_counts?: boolean;
        /** @description Also distinct companies, locations, sources and job types. */
        include_facets?: boolean;
        /** @description Such as fulltime or internship. */
        job_type?: string | null;
        limit?: number;
        /** @description Exactly this location text. */
        location?: string | null;
        offset?: number;
        /** @description Written in this language (ISO 639-1 code or name). */
        posting_language?: string | null;
        /** @description Written in another known language. */
        posting_language_not?: string | null;
        q?: string;
        /** @description Remote (true) or on site (false). */
        remote?: boolean | null;
        /** @description Postings that require this language. */
        requires?: string | null;
        /** @description likely_duplicate, no_longer_listed, language_required or pending (not computed yet). */
        signal?:
          | (
              | "likely_duplicate"
              | "no_longer_listed"
              | "language_required"
              | "pending"
            )
          | null;
        /** @description dismissed: latest dismissal first. */
        sort?: "newest" | "oldest" | "company" | "title" | "dismissed";
        /** @description The source a job summary names: a board or ATS (such as greenhouse), or manual. */
        source?: string | null;
        /** @description new, shortlisted, dismissed or active (not dismissed). */
        triage?: ("new" | "shortlisted" | "dismissed" | "active") | null;
        /** @description Jobs posted at this URL (board and redirect variants too). */
        url?: string | null;
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
  jobs_read: {
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
  jobs_link: {
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
        "application/json": components["schemas"]["LinkInput"];
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
  jobs_get: {
    parameters: {
      query: {
        /** @description Up to 20 job ids. */
        ids: string[];
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
          "application/json": components["schemas"]["JobBatch"];
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
  jobs_triage: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["JobTriage"];
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
        "application/json": components["schemas"]["ProviderUpdate"];
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
  skills_get: {
    parameters: {
      query?: {
        name?: string;
        path?: string;
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
          "application/json":
            components["schemas"]["Skill"] | components["schemas"]["SkillList"];
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
  skills_get_1: {
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
          "application/json":
            components["schemas"]["Skill"] | components["schemas"]["SkillList"];
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
  skills_file: {
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
      /** @description not_found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Error"];
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
          "application/json": components["schemas"]["SourceDetail"];
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
  sources_run_one: {
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
  sources_save: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["SourcesSave"];
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
  sources_run: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["SourceRunInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json":
            | components["schemas"]["SourcePreviewResult"]
            | components["schemas"]["Task"];
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
  templates_save: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["TemplateSave"];
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
      query?: never;
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
      query?: never;
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
  transfers_download: {
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
  transfers_upload: {
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
  workspace_context: {
    parameters: {
      query?: {
        /** @description Owner corrections since then (default: your previous read). */
        feedback_since?: string | null;
        /** @description career_full: full narratives and approved highlights; templates_full: TeX and guidance. */
        include?: ("career_full" | "templates_full")[];
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
          "application/json": components["schemas"]["WorkspaceContext"];
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
  health: {
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
