"""The PDF and optional TeX source of a CV or letter revision, and its readable text.

A CV or letter revision is complete once its PDF is stored; until then it is
incomplete and never counts for Ready. A complete revision is immutable: a change
is a new revision. When the revision has a TeX source, its PDF upload names the
source's SHA-256 (``source_sha256``), so a PDF compiled from another source is
refused before its bytes are stored; a PDF-only revision names none.

The readable text comes from the TeX source when there is one (``text.py``,
``text_from='tex'``), otherwise from the PDF (``pdf.py``, ``text_from='pdf'``). A
PDF whose text cannot be read leaves no text and does not stop the revision being
complete.
"""

from __future__ import annotations

from ..errors import DomainError
from .models import SOURCE_KINDS
from .text import decode_source, is_tex_source, revision_text

PDF = "application/pdf"


def media(media_type: str) -> str:
    return media_type.split(";", 1)[0].strip().lower()


def is_pdf(name: str, media_type: str) -> bool:
    return media(media_type) == PDF or name.lower().endswith(".pdf")


def _files(conn, document_id):
    # Plain tuples: the upgrade of a restored copy runs without a row factory.
    names = ("id", "name", "media_type", "sha256", "source_sha256")
    return [
        dict(zip(names, row, strict=True))
        for row in conn.execute(
            "SELECT id,name,media_type,sha256,source_sha256 FROM files WHERE document_id=? "
            "ORDER BY name,id",
            (document_id,),
        )
    ]


def is_complete(conn, document) -> bool:
    """Whether a CV or letter revision has its PDF stored (other kinds are never incomplete)."""
    if document["kind"] not in SOURCE_KINDS:
        return True
    return (
        conn.execute(
            "SELECT 1 FROM files WHERE document_id=? AND media_type=? LIMIT 1",
            (document["id"], PDF),
        ).fetchone()
        is not None
    )


def source_hash(conn, document_id) -> str | None:
    """The SHA-256 of the revision's TeX source, or None without one."""
    hashes = [
        file["sha256"]
        for file in _files(conn, document_id)
        if is_tex_source(file["name"], file["media_type"])
    ]
    return hashes[0] if len(hashes) == 1 else None


def check_upload(conn, document, name, media_type, sha256, source_sha256):
    """Refuse a file that would give a revision a second source or an unpaired PDF.

    Called when the upload is reserved (``sha256`` may be unknown) and again with
    the received bytes' hash. Re-sending a file under its own name is left to the
    caller's idempotent path.
    """
    files = [file for file in _files(conn, document["id"]) if file["name"] != name]
    sources = [file for file in files if is_tex_source(file["name"], file["media_type"])]
    source_kind = document["kind"] in SOURCE_KINDS
    pdf = is_pdf(name, media_type)
    if source_sha256 is not None and not pdf:
        raise DomainError(
            422, "source_sha256", "Only a PDF names the source it was built from (source_sha256)."
        )
    if is_tex_source(name, media_type):
        if source_kind and sources:
            raise DomainError(
                409,
                "source_exists",
                f"This revision already has its source ({sources[0]['name']}). "
                "Create a new revision for another source.",
                {"source": sources[0]["name"]},
            )
        paired = {file["source_sha256"] for file in files if file["source_sha256"]}
        if sha256 and paired and sha256 not in paired:
            raise DomainError(
                409,
                "source_mismatch",
                "The revision's PDF was built from another source.",
                {"pdf_source_sha256": sorted(paired)},
            )
        return
    if not pdf:
        return
    if source_kind and media(media_type) != PDF:
        raise DomainError(422, "pdf_media_type", "Upload the PDF with media type application/pdf.")
    if source_kind:
        others = [file for file in files if is_pdf(file["name"], file["media_type"])]
        if others:
            raise DomainError(
                409,
                "pdf_exists",
                f"This revision already has its PDF ({others[0]['name']}). "
                "Create a new revision for another PDF.",
            )
        if sources and source_sha256 is None:
            raise DomainError(
                422,
                "source_sha256_required",
                "This revision has a TeX source: upload the PDF built from it with "
                "source_sha256, the source's SHA-256.",
                {"source_sha256": sorted(file["sha256"] for file in sources)},
            )
    if source_sha256 is None:
        return
    hashes = {file["sha256"] for file in sources}
    if not hashes:
        raise DomainError(
            409,
            "source_required",
            "The PDF names a TeX source the revision does not have yet. Upload the source "
            "before its PDF, or upload the PDF without source_sha256 for a PDF-only revision.",
        )
    if source_sha256.lower() not in hashes:
        raise DomainError(
            409,
            "source_mismatch",
            "The PDF names a source this revision does not have. Compile the revision's "
            "source and upload that PDF, or create a new revision for the other source.",
            {"source_sha256": sorted(hashes)},
        )


def check_source_bytes(data: bytes):
    """A new source must be UTF-8 text, so its derived text is exact."""
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DomainError(
            422, "source_encoding", "Upload the .tex source encoded as UTF-8."
        ) from error


def sources_of(conn, document_id) -> list[tuple[str, str]]:
    """The revision's TeX sources as (name, text)."""
    found = []
    for file in _files(conn, document_id):
        if not is_tex_source(file["name"], file["media_type"]):
            continue
        blob = conn.execute(
            "SELECT content FROM blobs WHERE sha256=?", (file["sha256"],)
        ).fetchone()
        found.append((file["name"], decode_source(bytes(blob[0])) if blob else ""))
    return found


def refresh_text(conn, document_id):
    """Store the text derived from the revision's TeX sources, when it has one."""
    text = revision_text(sources_of(conn, document_id))
    if text is not None:
        conn.execute("UPDATE documents SET text=?,text_from='tex' WHERE id=?", (text, document_id))


def store_pdf_text(conn, document_id, text):
    """Store text read from the revision's PDF, unless its TeX source gave the text."""
    conn.execute(
        "UPDATE documents SET text=?,text_from=? WHERE id=? AND text_from IS NOT 'tex'",
        (text, "pdf" if text is not None else None, document_id),
    )
