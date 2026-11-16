# Server rules

The server refuses some steps, with an error code and a message. Each row says
when, and the way through. A refused batch item leaves its record unchanged.

| Code or case | When | The way through |
|---|---|---|
| application_has_work | Triage a shortlisted job back to new or dismissed while its application has documents, notes, requirements, answers, replies or a stage change | Close the application as not pursued, with a note; the job stays shortlisted |
| application_not_sent | A reply, or a close as no response, on an application not recorded as sent | When the owner says they sent it: in one `applications_update`, first an item with stage applied and applied_on, then the reply in a second item (items apply in order) |
| reply_stage | A reply and a stage, outcome or concluded_on in one item | A reply sets the stage itself: send it alone |
| reply_exists | A second reply of the same kind on the same day | It is already recorded; correct it with reply_fix |
| application_has_replies | Back to Shortlisted with a reply recorded | Remove a mistaken reply with reply_fix first; otherwise keep the stage |
| application_in_progress | Start, reopen or merge while the job has another open application | Continue that one, or close one first |
| A dismissed job | `applications_create` or a reopen on a dismissed job | `jobs_triage` to shortlisted starts its application; reopen only when the owner asks |
| Revision currentness | A revision is current once created with previous_id, and complete once its PDF is stored | Upload at once. On a failed upload, `documents_delete` the empty revision (the previous one is current again) or create again with the same idempotency key for a new grant |
| revision_complete | Adding a file to a complete revision | Revisions are final: create a new one with previous_id |
| unapproved_highlight | Citing a highlight that is not approved | Cite approved highlights only, or ask the owner to approve the wording |
| triage_reason | A reason with new or shortlisted | Give a reason only when dismissing |
| A paused new source | `sources_save` without enabled true | Save new sources with enabled true unless the owner wants them paused |
| Idempotency key used for another request (409) | A retry whose content changed | The first record exists: read it and update it instead |
| Version conflict (409) | The record changed since you read it | Read it again, keep the owner's change, redo yours if it still holds |
