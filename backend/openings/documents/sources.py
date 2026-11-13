"""The source and PDF of a revision: which file is which, their pairing and the derived text.

A CV or letter revision has one TeX source and one PDF built from it. The PDF
upload names the source's SHA-256 (``source_sha256``), so a PDF compiled from
another source is refused before its bytes are stored. The revision's readable
text is derived from its source when the source arrives (``text.py``).
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
        if source_sha256 is None:
            raise DomainError(
                422,
                "source_required",
                "Upload the revision's .tex source first, then the PDF with source_sha256, "
                "the SHA-256 of the source it was built from.",
            )
    if source_sha256 is None:
        return
    hashes = {file["sha256"] for file in sources}
    if not hashes:
        raise DomainError(
            409,
            "source_required",
            "The revision has no .tex source yet. Upload the source before its PDF.",
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
    """Store the text derived from the revision's sources (NULL without one)."""
    conn.execute(
        "UPDATE documents SET text=? WHERE id=?",
        (revision_text(sources_of(conn, document_id)), document_id),
    )


def approval_problem(conn, document) -> DomainError | None:
    """Why a CV or letter revision cannot be approved yet, if it cannot."""
    if document["kind"] not in SOURCE_KINDS:
        return None
    files = _files(conn, document["id"])
    sources = [file for file in files if is_tex_source(file["name"], file["media_type"])]
    pdfs = [file for file in files if media(file["media_type"]) == PDF]
    if not sources:
        return DomainError(
            409,
            "source_required",
            "Upload the revision's .tex source before approving it: its text is what you review.",
        )
    if not pdfs:
        return DomainError(
            409, "pdf_required", "Upload the PDF built from the source before approving it."
        )
    hashes = {file["sha256"] for file in sources}
    if any(file["source_sha256"] and file["source_sha256"] not in hashes for file in pdfs):
        return DomainError(409, "source_mismatch", "The PDF was built from another source.")
    return None
