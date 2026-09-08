"""Text normalization shared by scoring, sources and search."""

from __future__ import annotations

import re
import unicodedata

_STOP_WORDS = frozenset(
    """
    a an the and or but in on at to for of with by from as is was are were been
    be have has had do does did will would could should may might must shall
    can need that this these those it its we you they i he she who what which
    where when why how
    """.split()
)


def normalize_text(text: str | None) -> str:
    """Lower-case and strip diacritics (``Zürich`` -> ``zurich``)."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", str(text))
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))
    return stripped.replace("ß", "ss").lower()


def extract_words(text: str | None) -> list[str]:
    """Meaningful words from free text, without stop words and one-letter tokens."""
    if not text:
        return []
    words = re.findall(r"\b[a-z0-9+#]+\b", normalize_text(text))
    return [word for word in words if word not in _STOP_WORDS and len(word) > 1]
