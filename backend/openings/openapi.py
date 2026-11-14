"""The OpenAPI document: error model, authentication, tags and access per operation.

``uv run python -m openings.openapi`` prints it without starting a server; the
dashboard's TypeScript types are generated from it (``npm run api:gen``).
"""

import inspect
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, ConfigDict, Field

from .auth import COOKIE
from .interfaces.operation import OWNER, READ

ERROR_CODES = {
    401: "unauthorized: sign in or send a valid bearer token (also transfer_token, transfer_expired, transfer_used: a grant works once).",
    403: "forbidden: an agent token on an owner-only operation; csrf: a browser write without its X-CSRF-Token header.",
    404: "not_found: the record or route does not exist, including a record the body names (application_id, career_id...).",
    409: "conflict: the record changed (details.current_version and details.id); also constraint, application_has_work and similar rule conflicts.",
    413: "request_size or file_size: the body or file is over its limit.",
    422: "validation: details lists {field, message, type} per invalid field; other codes name a rule.",
    429: "rate_limited: the shared provider gate is waiting; details.retry_after_seconds and the Retry-After header give the wait.",
}


class ErrorBody(BaseModel):
    code: str = Field(description="A stable machine code, such as validation or conflict.")
    status: int = Field(description="The HTTP status.")
    message: str = Field(description="A sentence for a person.")
    details: Any = Field(
        default=None,
        description="Structured details: field errors for validation, current_version and id for a version conflict.",
    )


class Error(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "description": "Every error response. Codes by status: "
            + " ".join(f"{status} {text}" for status, text in ERROR_CODES.items())
        }
    )

    error: ErrorBody


def _names_a_record(op):
    """Whether a write's body names a record that must exist (application_id, career_id...)."""
    if op.method not in ("POST", "PUT", "PATCH"):
        return False
    for parameter in inspect.signature(op.fn, eval_str=True).parameters.values():
        model = parameter.annotation
        if isinstance(model, type) and issubclass(model, BaseModel):
            return any(name.endswith("_id") for name in model.model_fields)
    return False


def errors(op, path):
    """The error responses an operation documents."""
    statuses = [401, 403, 422]
    if "{" in path or _names_a_record(op):
        statuses.append(404)
    if op.access != READ:
        statuses.append(409)
    if op.method in ("POST", "PUT", "PATCH"):
        statuses.append(413)
    if op.open_world:
        statuses.append(429)
    return {
        status: {"model": Error, "description": ERROR_CODES[status].split(":")[0]}
        for status in sorted(statuses)
    }


TAGS = [
    ("workspace", "The start read, identity, sessions, the change log, skills and backup."),
    ("jobs", "Archived postings, triage, duplicates and the timeline."),
    ("notes", "Notes on jobs and applications."),
    ("applications", "Applications, replies, readiness and Stats."),
    ("documents", "CV, letter and form-answer revisions."),
    ("files", "File metadata and byte transfers."),
    ("career", "Profile and career entries, and their import."),
    ("highlights", "Reusable wording tied to career entries."),
    ("templates", "CV and letter templates."),
    ("preferences", "The owner's Preferences and settings."),
    ("sources", "Saved searches and company feeds."),
    ("collection", "The collection switch, providers, runs and tasks."),
    (
        "owner",
        "Owner-only operations: never available to an agent token or over MCP (password, tokens, restore, export, career import, kept backups).",
    ),
]


# Request examples by operationId: the batch operations and the upload sequence.
EXAMPLES = {
    "jobs_triage": {
        "dismiss": {
            "summary": "Dismiss two jobs with a reason and shortlist a third",
            "value": {
                "items": [
                    {
                        "job_id": "j_01",
                        "to": "dismissed",
                        "reason": "Junior role; I look for senior roles.",
                    },
                    {"job_id": "j_02", "to": "dismissed", "reason": "Requires German."},
                    {"job_id": "j_03", "to": "shortlisted"},
                ]
            },
        },
        "restore": {
            "summary": "Restore them to review",
            "value": {"items": [{"job_id": "j_01", "to": "new"}, {"job_id": "j_02", "to": "new"}]},
        },
    },
    "applications_update": {
        "reply": {
            "summary": "Record an interview invitation and close an overdue application",
            "value": {
                "items": [
                    {
                        "application_id": "a_01",
                        "reply": {"kind": "interview", "note": "Call on Monday."},
                    },
                    {"application_id": "a_02", "stage": "closed", "outcome": "no_response"},
                ]
            },
        }
    },
    "sources_save": {
        "add": {
            "summary": "Add a company board, paused, and pause an existing source",
            "value": {
                "items": [
                    {"name": "Example GmbH", "url": "https://boards.greenhouse.io/example"},
                    {"source_id": "s_01", "expected_version": 3, "enabled": False},
                ]
            },
        }
    },
    "files_upload": {
        "upload": {
            "summary": "Step 1 of 2: reserve; then PUT the bytes to the returned url",
            "description": "PUT the exact bytes to the returned url with the returned headers "
            "(X-Transfer-Token); the PUT returns the stored file.",
            "value": {
                "owner_type": "career",
                "owner_id": "k_01",
                "name": "certificate.pdf",
                "size": 48213,
                "media_type": "application/pdf",
            },
        }
    },
    "documents_create": {
        "cv": {
            "summary": "A CV revision with its TeX source inline; PUT its PDF to uploads.pdf",
            "value": {
                "application_id": "a_01",
                "kind": "cv",
                "title": "CV for Example GmbH",
                "pdf": {"name": "cv.pdf", "size": 48213},
                "source": "\\documentclass{article}\\begin{document}Alex Example\\end{document}",
                "highlight_ids": ["h_01"],
            },
        }
    },
}

AUTHENTICATION = """
Send `Authorization: Bearer <token>` (an owner or agent API token). The dashboard
uses the `openings_session` cookie instead, and sends `X-CSRF-Token` (from
`GET /api/v1/auth/session`) on every write. Operations marked
`x-openings-access: owner` refuse an agent token with 403 forbidden. Byte transfers
use the `X-Transfer-Token` or `X-Operational-Token` header of a grant.
"""


def build(app):
    """The OpenAPI document of ``app``, built once and cached."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title="Openings",
        version=app.version,
        description=(app.description or "").strip() + "\n" + AUTHENTICATION,
        routes=app.routes,
        tags=[{"name": name, "description": text} for name, text in TAGS],
    )
    components = schema.setdefault("components", {})
    components["securitySchemes"] = {
        "bearerAuth": {"type": "http", "scheme": "bearer", "description": "An API token."},
        "sessionCookie": {"type": "apiKey", "in": "cookie", "name": COOKIE},
        "csrfHeader": {"type": "apiKey", "in": "header", "name": "X-CSRF-Token"},
    }
    schema["security"] = [{"bearerAuth": []}, {"sessionCookie": [], "csrfHeader": []}]
    owner = "Owner only: an agent token is refused with 403 forbidden; not an MCP tool."
    error = {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}
    for name in ("HTTPValidationError", "ValidationError"):
        components["schemas"].pop(name, None)
    for item in schema["paths"].values():
        for operation in item.values():
            # A transport route's errors are the Error model too.
            for code, response in operation["responses"].items():
                if code[0] in "45" and (
                    "content" not in response or "HTTPValidationError" in json.dumps(response)
                ):
                    response["content"] = error
            if operation.get("operationId") in EXAMPLES:
                body = operation["requestBody"]["content"]["application/json"]
                body["examples"] = EXAMPLES[operation["operationId"]]
            if operation.get("x-openings-access") == OWNER:
                operation["description"] = (
                    operation.get("description", "") + "\n\n" + owner
                ).strip()
    app.openapi_schema = schema
    return schema


def main():
    from .app import create_app

    with tempfile.TemporaryDirectory() as directory:
        app = create_app(Path(directory) / "openapi.sqlite", start_worker=False)
        json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
