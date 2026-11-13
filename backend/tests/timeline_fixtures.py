"""An application whose standing guidance is its pinned note."""


def guided_application(workspace, job_id, text, **fields):
    """Start an application whose standing guidance is its pinned note.

    Before 0.23 the deprecated ``note`` field of a create did the same.
    """
    application = workspace.create_application({"job_id": job_id, **fields})
    workspace.add_note(job_id, {"body": text, "application_id": application["id"], "pinned": True})
    return workspace.get_application(application["id"])
