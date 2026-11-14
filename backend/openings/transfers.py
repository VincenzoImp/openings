"""Close SQLite readers on their owning thread before serving portable byte snapshots."""

import json
import tempfile

from fastapi.responses import StreamingResponse


class SnapshotResponse(StreamingResponse):
    def __init__(self, content, *, media_type, headers=None):
        self.snapshot = tempfile.TemporaryFile()  # noqa: SIM115 - closed after streaming
        try:
            for chunk in content:
                self.snapshot.write(chunk)
            size = self.snapshot.tell()
            self.snapshot.seek(0)

            def chunks():
                while chunk := self.snapshot.read(64 * 1024):
                    yield chunk

            super().__init__(
                chunks(),
                media_type=media_type,
                headers={**(headers or {}), "Content-Length": str(size)},
            )
        except BaseException:
            self.snapshot.close()
            raise

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.snapshot.close()


class RecordsResponse(SnapshotResponse):
    """Prepare the SQLite snapshot on one thread before streaming file bytes."""

    def __init__(self, records):
        super().__init__(
            (record.encode("utf-8") for record in records),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="openings-export.json"'},
        )


SECRET_KEYS = {
    "api_key",
    "apikey",
    "app_key",
    "access_token",
    "api_token",
    "client_secret",
    "password",
    "token",
    "secret",
    "authorization",
    "cookie",
}


def redact_secrets(value):
    if isinstance(value, dict):
        return {
            key: redact_secrets(item)
            for key, item in value.items()
            if key.lower().replace("-", "_") not in SECRET_KEYS
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value


# The exported tables, each with its JSON columns.
EXPORT_TABLES = {
    "jobs": ["metadata", "overrides"],
    "job_signals": ["required", "distinct_from"],
    "postings": ["payload"],
    "applications": ["questions", "answers", "requirements", "required_documents"],
    "replies": [],
    "notes": [],
    "events": ["payload"],
    "knowledge": ["metadata", "dates", "skills"],
    "claims": ["metadata"],
    "templates": ["rules"],
    "preference_sections": ["items"],
    "documents": ["content", "claim_ids", "knowledge_ids"],
    "files": [],
    "sources": ["config", "schedule"],
    "providers": ["policy", "runtime"],
}


def export_records(db):
    """The portable JSON records of the workspace, without file bytes or credentials."""
    yield '{"format":"openings-records-v1","files_include_bytes":false'
    with db.connect() as conn:
        conn.execute("BEGIN")
        for table, json_fields in EXPORT_TABLES.items():
            yield ',"' + table + '":['
            first = True
            for row in conn.execute("SELECT * FROM " + table):
                item = dict(row)
                for key in json_fields:
                    if item[key] is not None:
                        item[key] = json.loads(item[key])
                if table == "sources":
                    item["config"] = redact_secrets(item["config"])
                yield ("" if first else ",") + json.dumps(item, ensure_ascii=False)
                first = False
            yield "]"
        settings = {}
        for row in conn.execute(
            "SELECT key,data FROM settings WHERE key IN ('profile','workspace','collection')"
        ):
            settings[row["key"]] = redact_secrets(json.loads(row["data"]))
        yield ',"settings":' + json.dumps(settings, ensure_ascii=False) + "}"
