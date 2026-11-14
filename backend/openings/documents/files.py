"""Files owned by exact records and the scoped, single-use transfer grants."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from urllib.parse import quote

from fastapi import Request

from .. import events
from ..actors import current_actor, from_columns
from ..common import check_page, check_version, encode, get_row, new_id, now
from ..errors import DomainError, conflict, missing
from ..snapshots import SnapshotResponse
from .models import OWNER_COLUMNS, OWNER_TABLES, SOURCE_KINDS, OwnerType, UploadReservation
from .pdf import pdf_text
from .sources import (
    PDF,
    check_source_bytes,
    check_upload,
    is_complete,
    is_pdf,
    media,
    refresh_text,
    store_pdf_text,
)
from .text import is_tex_source

FILE_VERSION = 1


def drop_grants(conn, **match):
    """Delete the transfer grants whose payload has every ``key=value`` of ``match``."""
    where = " AND ".join(f"json_extract(payload,'$.{key}')=?" for key in match)
    conn.execute(f"DELETE FROM transfer_grants WHERE {where}", tuple(match.values()))


class FileOperations:
    """Reading, uploading, downloading and deleting files."""

    def _owner(self, conn, owner_type, owner_id, *, writable=False):
        if owner_type not in OWNER_COLUMNS:
            raise DomainError(422, "owner_type", "Unsupported file owner type.")
        row = get_row(conn, OWNER_TABLES[owner_type], owner_id, "File owner")
        if (
            writable
            and owner_type == "document"
            and row["kind"] in SOURCE_KINDS
            and is_complete(conn, row)
        ):
            raise DomainError(
                409,
                "revision_complete",
                "This revision is complete (its PDF is stored) and cannot change. "
                "Create a new revision with previous_id instead.",
            )
        if owner_type == "job":
            return row, row["id"]
        if owner_type == "document":
            application = get_row(conn, "applications", row["application_id"], "Application")
            return row, application["job_id"]
        return row, None

    def _file_record(self, row):
        result = {
            key: row[key] for key in ["id", "sha256", "name", "media_type", "size", "created_at"]
        }
        for owner, column in OWNER_COLUMNS.items():
            if row.get(column) is not None:
                result.update(owner_type=owner, owner_id=row[column])
                break
        # A revision's PDF names the SHA-256 of the source it was built from.
        result["source_sha256"] = row.get("source_sha256")
        result["url"] = f"/api/v1/files/{row['id']}/content"
        # A file never changes, so its version is always 1; a delete names it.
        result["version"] = FILE_VERSION
        return result

    def get_file(self, file_id: str) -> dict:
        """Read immutable file metadata and its authenticated content URL, not binary bytes."""
        row = self.db.one("SELECT * FROM files WHERE id=?", (file_id,))
        if not row:
            missing("File")
        return self._file_record(row)

    def list_files(
        self,
        owner_type: OwnerType | None = None,
        owner_id: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = True,
        q: str = "",
        media_type: str = "",
        application_id: str = "",
    ) -> dict:
        """List file metadata by owner, name/media type or application revisions. Metadata is always compact, including with summary=true; fetch bytes through a scoped HTTP transfer."""
        check_page(limit, offset)
        if owner_id and not owner_type:
            raise DomainError(422, "file_owner", "Provide owner_type when filtering by owner_id.")
        where, params = [], []
        if owner_type:
            if owner_type not in OWNER_COLUMNS:
                raise DomainError(422, "owner_type", "Unsupported file owner type.")
            if owner_id:
                where.append(f"{OWNER_COLUMNS[owner_type]}=?")
                params.append(owner_id)
            else:
                where.append(f"{OWNER_COLUMNS[owner_type]} IS NOT NULL")
        if q:
            where.append("name LIKE ?")
            params.append(f"%{q}%")
        if media_type:
            where.append("media_type=?")
            params.append(media_type)
        if application_id:
            where.append("document_id IN (SELECT id FROM documents WHERE application_id=?)")
            params.append(application_id)
        clause = " WHERE " + " AND ".join(where) if where else ""
        rows = self.db.all(
            f"SELECT * FROM files{clause} ORDER BY created_at,name,id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        return {
            "items": [self._file_record(row) for row in rows],
            "total": self.db.one(f"SELECT COUNT(*) AS n FROM files{clause}", params)["n"],
            "limit": limit,
            "offset": offset,
        }

    def _new_grant(self, conn, payload, method):
        token = secrets.token_urlsafe(32)
        expires = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
        conn.execute("DELETE FROM transfer_grants WHERE expires_at<?", (now(),))
        conn.execute(
            "INSERT INTO transfer_grants(token_hash,payload,method,expires_at) VALUES(?,?,?,?)",
            (hashlib.sha256(token.encode()).hexdigest(), encode(payload), method, expires),
        )
        return {
            "url": "/api/v1/transfers",
            "method": method,
            "headers": {"X-Transfer-Token": token},
            "expires_at": expires,
            "max_bytes": payload.get("size"),
        }

    def reserve_upload(self, value: UploadReservation) -> dict:
        """Reserve a short-lived bounded PUT transfer for one owner/name/size. Send raw bytes using returned URL/headers; SHA-256 is optional and verified when supplied."""
        if value.size > self.max_file_bytes:
            raise DomainError(
                413, "file_size", f"Files must be at most {self.max_file_bytes} bytes."
            )
        if value.source_sha256 is not None and value.owner_type != "document":
            raise DomainError(
                422, "source_sha256", "Only a document revision's PDF names its source."
            )
        with self.db.transaction() as conn:
            return self.upload_grant(conn, value)

    def upload_grant(self, conn, value: UploadReservation, pending_source=None) -> dict:
        """A one-shot PUT grant for one file of an owner, checked in the caller's transaction."""
        owner, job_id = self._owner(conn, value.owner_type, value.owner_id, writable=True)
        payload = value.model_dump()
        payload["sha256"] = value.sha256.lower() if value.sha256 else None
        payload["source_sha256"] = value.source_sha256.lower() if value.source_sha256 else None
        if value.owner_type == "document":
            check_upload(
                conn,
                owner,
                value.name,
                value.media_type,
                payload["sha256"],
                payload["source_sha256"],
                pending_source,
            )
        payload["job_id"] = job_id
        # The raw upload carries only the grant, so the grant remembers who reserved it.
        payload["actor"] = list(current_actor().columns())
        return self._new_grant(conn, payload, "PUT")

    def reserve_download(self, file_id: str) -> dict:
        """Obtain a short-lived GET transfer for one existing file; resolve its URL against this workspace origin."""
        with self.db.transaction() as conn:
            row = get_row(conn, "files", file_id, "File")
            descriptor = self._file_record(row)
            _, job_id = self._owner(conn, descriptor["owner_type"], descriptor["owner_id"])
            return self._new_grant(
                conn, {"file_id": file_id, "job_id": job_id, "size": row["size"]}, "GET"
            )

    def _grant(self, token, method, conn=None):
        if not token:
            raise DomainError(401, "transfer_token", "A valid transfer token is required.")
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        query = ("SELECT * FROM transfer_grants WHERE token_hash=?", (token_hash,))
        row = conn.execute(*query).fetchone() if conn is not None else self.db.one(*query)
        row = dict(row) if row else None
        if not row or row["expires_at"] <= now():
            raise DomainError(401, "transfer_token", "This transfer token is invalid or expired.")
        if row["method"] != method:
            raise DomainError(
                403, "transfer_method", "The transfer token does not permit this operation."
            )
        return row, json.loads(row["payload"])

    async def upload(self, request: Request):
        async with self._upload_slots:
            return await self._upload(request)

    async def _upload(self, request: Request):
        token = request.headers.get("X-Transfer-Token", "")
        _, scope = self._grant(token, "PUT")
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > min(scope["size"], self.max_file_bytes):
                raise DomainError(413, "file_size", "Uploaded bytes exceed the reserved size.")
            data.extend(chunk)
        if len(data) != scope["size"]:
            raise DomainError(422, "file_size", "Uploaded bytes do not match the reserved size.")
        actual_sha = hashlib.sha256(data).hexdigest()
        if scope.get("sha256") and actual_sha != scope["sha256"]:
            raise DomainError(422, "file_hash", "Uploaded bytes do not match the declared SHA-256.")
        if media(scope["media_type"]) == PDF and not data.startswith(b"%PDF-"):
            raise DomainError(422, "pdf_header", "The uploaded file is not a PDF.")
        document = scope["owner_type"] == "document"
        source = document and is_tex_source(scope["name"], scope["media_type"])
        if source:
            check_source_bytes(bytes(data))
        # The text of a PDF is read before the write transaction; it is kept only for
        # a revision without a TeX source.
        pdf = document and is_pdf(scope["name"], scope["media_type"])
        # A PDF naming its source gets its text from that source instead.
        text = pdf_text(bytes(data)) if pdf and not scope.get("source_sha256") else None
        with self.db.transaction() as conn:
            grant, current = self._grant(token, "PUT", conn)
            self._owner(conn, current["owner_type"], current["owner_id"], writable=False)
            if grant["used"]:
                file_id = current.get("file_id")
                existing = get_row(conn, "files", file_id, "Completed upload") if file_id else None
                if existing and existing["sha256"] == actual_sha:
                    return self._file_record(existing)
                raise DomainError(
                    401, "transfer_used", "This upload grant was already used. Reserve another."
                )
            owner, _ = self._owner(conn, current["owner_type"], current["owner_id"], writable=True)
            column = OWNER_COLUMNS[current["owner_type"]]
            old = conn.execute(
                f"SELECT * FROM files WHERE {column}=? AND name=?",
                (current["owner_id"], current["name"]),
            ).fetchone()
            if old and old["sha256"] != actual_sha:
                conflict(
                    "A different file already uses this name. Create a document revision or remove the mutable asset first."
                )
            if old:
                file_id = old["id"]
            else:
                if current["owner_type"] == "document":
                    check_upload(
                        conn,
                        owner,
                        current["name"],
                        current["media_type"],
                        actual_sha,
                        current.get("source_sha256"),
                    )
                file_id = new_id()
                if pdf and media(current["media_type"]) == PDF:
                    # Stored without parameters, as Ready and completeness compare it.
                    current["media_type"] = PDF
                conn.execute(
                    "INSERT OR IGNORE INTO blobs(sha256,content,size) VALUES(?,?,?)",
                    (actual_sha, bytes(data), len(data)),
                )
                conn.execute(
                    f"INSERT INTO files(id,sha256,name,media_type,size,{column},created_at,source_sha256) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (
                        file_id,
                        actual_sha,
                        current["name"],
                        current["media_type"],
                        len(data),
                        current["owner_id"],
                        now(),
                        current.get("source_sha256"),
                    ),
                )
                if current["owner_type"] in {"template", "career"}:
                    conn.execute(
                        f"UPDATE {OWNER_TABLES[current['owner_type']]} SET version=version+1,updated_at=? WHERE id=?",
                        (now(), current["owner_id"]),
                    )
                elif current["owner_type"] == "document":
                    conn.execute(
                        "UPDATE documents SET version=version+1 WHERE id=?", (current["owner_id"],)
                    )
                    if source:
                        refresh_text(conn, current["owner_id"])
                    elif pdf and owner["kind"] in SOURCE_KINDS:
                        store_pdf_text(conn, current["owner_id"], text)
                uploader = from_columns(*(current.get("actor") or ()))
                self._file_event(
                    conn,
                    "file_uploaded",
                    file_id,
                    current["owner_type"],
                    current["owner_id"],
                    current.get("job_id"),
                    uploader,
                )
            current["file_id"] = file_id
            conn.execute(
                "UPDATE transfer_grants SET used=1,payload=? WHERE token_hash=?",
                (encode(current), grant["token_hash"]),
            )
            result = get_row(conn, "files", file_id, "File")
        return self._file_record(result)

    def _file_event(self, conn, kind, file_id, owner_type, owner_id, job_id, actor=None):
        application_id = None
        if owner_type == "document":
            application_id = get_row(conn, "documents", owner_id, "Document revision")[
                "application_id"
            ]
        events.record(
            conn,
            kind,
            subject=("file", file_id),
            payload={"file_id": file_id, "owner_type": owner_type, "owner_id": owner_id},
            job_id=job_id,
            application_id=application_id,
            actor=actor,
        )

    def file_response(self, file_id: str, inline: bool = True):
        row = self.db.one("SELECT * FROM files WHERE id=?", (file_id,))
        if not row:
            missing("File")
        media_type = row["media_type"].split(";", 1)[0]
        disposition = (
            "inline"
            if inline and media_type in {"application/pdf", "image/png", "image/jpeg", "image/webp"}
            else "attachment"
        )
        filename = quote(PurePosixPath(row["name"]).name, safe="")

        def chunks():
            with self.db.connect() as conn:
                blob_row = conn.execute(
                    "SELECT rowid AS blob_rowid FROM blobs WHERE sha256=?", (row["sha256"],)
                ).fetchone()
                if not blob_row:
                    missing("File bytes")
                with conn.blobopen(
                    "blobs", "content", blob_row["blob_rowid"], readonly=True
                ) as blob:
                    while chunk := blob.read(64 * 1024):
                        yield chunk

        return SnapshotResponse(
            chunks(),
            media_type=media_type,
            headers={
                "Content-Length": str(row["size"]),
                "Content-Disposition": f"{disposition}; filename*=UTF-8''{filename}",
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, no-store",
                "Content-Security-Policy": "sandbox; default-src 'none'; frame-ancestors 'self'",
            },
        )

    def download(self, request: Request):
        """Stream a file under a download grant; like every grant, it works once."""
        token = request.headers.get("X-Transfer-Token", "")
        with self.db.transaction() as conn:
            grant, payload = self._grant(token, "GET", conn)
            if grant["used"]:
                raise DomainError(
                    401, "transfer_used", "This download grant was already used. Reserve another."
                )
            conn.execute(
                "UPDATE transfer_grants SET used=1 WHERE token_hash=?", (grant["token_hash"],)
            )
        return self.file_response(payload["file_id"], inline=False)

    def delete_file(self, file_id: str, expected_version: int) -> dict:
        """Permanently delete a live Career entry, template or job asset, with its expected_version (a file's version is always 1). Revision files are immutable: delete the revision instead."""
        with self.db.transaction() as conn:
            row = get_row(conn, "files", file_id, "File")
            descriptor = self._file_record(row)
            check_version(descriptor, expected_version)
            if descriptor["owner_type"] == "document":
                conflict(
                    "Revision files are immutable. Delete the entire document or create a new revision."
                )
            conn.execute("DELETE FROM files WHERE id=?", (file_id,))
            self._file_event(
                conn,
                "file_deleted",
                file_id,
                descriptor["owner_type"],
                descriptor["owner_id"],
                row["job_id"],
            )
            if descriptor["owner_type"] in {"career", "template"}:
                conn.execute(
                    f"UPDATE {OWNER_TABLES[descriptor['owner_type']]} SET version=version+1,updated_at=? WHERE id=?",
                    (now(), descriptor["owner_id"]),
                )
            drop_grants(conn, file_id=file_id)
        self.db.collect_blobs()
        return {"deleted": True, "id": file_id}
