"""Readable text of a PDF, for a CV or letter revision without a TeX source.

``pypdf`` is pure Python (no TeX runtime, no system library), pinned in
``uv.lock``. Extraction is best effort: a PDF it cannot read gives no text, and a
revision without text is still complete. Its layout mode is not used, so the text
reads as the PDF's text runs in order, one line per line of the page.
"""

import io
import logging

LOG = logging.getLogger(__name__)

# Bounds for one extraction: pages read and characters kept.
MAX_PAGES = 50
MAX_CHARACTERS = 400_000


def pdf_text(data: bytes) -> str | None:
    """The text of a PDF's pages, or None when it cannot be read or holds no text."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages[:MAX_PAGES]:
            pages.append(page.extract_text() or "")
    except Exception as error:  # noqa: BLE001 - any unreadable PDF gives no text
        LOG.info("No text from a PDF (%s).", type(error).__name__)
        return None
    lines = [line.rstrip() for page in pages for line in page.splitlines()]
    text = "\n".join(lines).strip()[:MAX_CHARACTERS]
    return text or None
