"""Compare a revision's structured content with the text of its attached LaTeX source.

The check needs no TeX runtime: it strips common markup from the uploaded ``.tex``
text and compares word sequences. Each text value in the structured content must
appear, as a contiguous word sequence, somewhere in the source. Case, whitespace,
punctuation, accents and LaTeX markup are ignored; changed, added or removed words
are reported.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

TEX_MEDIA_TYPES = {"application/x-tex", "text/x-tex", "application/x-latex", "text/x-latex"}
# Structured-content keys that hold identifiers or presentation settings, not visible text.
SKIPPED_KEYS = {
    "id",
    "ids",
    "kind",
    "type",
    "format",
    "style",
    "layout",
    "template",
    "version",
    "language",
    "lang",
    "locale",
    "media_type",
    "file",
    "filename",
    "path",
    "schema",
}
IGNORED_TOKENS = {"http", "https", "www", "mailto"}
MAX_REPORTED = 50

_LETTERS = {"ss": "ss", "i": "i", "j": "j", "o": "o", "O": "O", "l": "l", "L": "L"}
_LETTERS.update({"ae": "ae", "AE": "AE", "oe": "oe", "OE": "OE", "aa": "a", "AA": "A"})
_FOLD = str.maketrans(
    {"ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ł": "l", "Ł": "L"}
)
# Commands whose arguments are settings rather than visible text, by argument count.
_LAYOUT = {
    1: "vspace|hspace|includegraphics|label|ref|pageref|eqref|cite|color|pagecolor|linespread"
    "|usepackage|documentclass|geometry|hypersetup|pagestyle|thispagestyle|newgeometry"
    "|textcolor|colorbox|raisebox",
    2: "setlength|addtolength|setcounter|fontsize|rule|multicolumn",
    3: "definecolor",
}
_ENVIRONMENT_ARGUMENTS = {
    1: "tabular|minipage|multicols|longtable|array|wrapfigure",
    2: "tabularx|tabular\\*",
}
_OPTIONAL = r"(?:\s*\[[^\]]*\])?"
_ARGUMENT = r"(?:\s*\{[^{}]*\})"


def is_tex_source(name: str, media_type: str) -> bool:
    lowered = name.lower()
    return lowered.endswith((".tex", ".ltx")) or media_type.split(";", 1)[0] in TEX_MEDIA_TYPES


def strip_comments(source: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in source.splitlines())


def _strip_markup(text: str) -> str:
    text = re.sub(
        r"\\(ss|ae|AE|oe|OE|aa|AA|i|j|o|O|l|L)(?![A-Za-z])\s*(?:\{\})?",
        lambda match: _LETTERS[match.group(1)],
        text,
    )
    text = re.sub(r"\\([cvuHkrbd])\s*\{\s*([A-Za-z])\s*\}", r"\2", text)
    text = re.sub(r"\\(['\"^`~=.])\s*\{\s*([A-Za-z])\s*\}", r"\2", text)
    text = re.sub(r"\\(['\"^`~=.])([A-Za-z])", r"\2", text)
    text = text.replace("\\-", "")
    text = re.sub(r"\\\\\*?" + _OPTIONAL, " ", text)
    text = re.sub(r"\\(?:kern|hskip|vskip)\s*-?[\d.]+\s*[a-z]{2}", " ", text)
    for count, names in sorted(_ENVIRONMENT_ARGUMENTS.items(), reverse=True):
        text = re.sub(rf"\\begin\s*\{{(?:{names})\}}{_OPTIONAL}{_ARGUMENT}{{{count}}}", " ", text)
    text = re.sub(r"\\(?:begin|end)\s*\{[^{}]*\}" + _OPTIONAL, " ", text)
    for count, names in sorted(_LAYOUT.items(), reverse=True):
        text = re.sub(rf"\\(?:{names})\*?(?![A-Za-z]){_OPTIONAL}{_ARGUMENT}{{{count}}}", " ", text)
    text = re.sub(r"\\[A-Za-z@]+\*?", " ", text)
    text = re.sub(r"\\(.)", r"\1", text)
    return text.replace("~", " ")


def tokens(text: str, *, markup: bool = True) -> list[str]:
    """Normalize text to comparable words, ignoring case, accents and punctuation."""
    if markup:
        text = _strip_markup(text)
    text = unicodedata.normalize("NFKD", text.translate(_FOLD))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return [
        token for token in re.findall(r"[^\W_]+", text.casefold()) if token not in IGNORED_TOKENS
    ]


def content_texts(content: Any, path: str = "") -> list[tuple[str, str]]:
    """Collect visible text values with their JSON paths, skipping identifiers and settings."""
    found: list[tuple[str, str]] = []
    if isinstance(content, dict):
        for key, value in content.items():
            name = str(key)
            lowered = name.lower()
            if (
                lowered in SKIPPED_KEYS
                or lowered.endswith(("_id", "_ids"))
                or lowered.startswith("_")
            ):
                continue
            found.extend(content_texts(value, f"{path}.{name}" if path else name))
    elif isinstance(content, list):
        for index, value in enumerate(content):
            found.extend(content_texts(value, f"{path}[{index}]"))
    elif isinstance(content, str) and content.strip():
        found.append((path or "$", content))
    return found


def compare(content: Any, sources: list[tuple[str, str]]) -> dict:
    """Compare structured content with named LaTeX sources and report missing text."""
    texts = content_texts(content)
    if not sources:
        return {
            "status": "not_checked",
            "reason": "No .tex source file is attached to this revision.",
            "checked": 0,
            "mismatch_count": 0,
            "mismatches": [],
        }
    if not texts:
        return {
            "status": "not_checked",
            "reason": "The structured content contains no text values.",
            "checked": 0,
            "mismatch_count": 0,
            "mismatches": [],
        }
    haystack = (
        " " + " ".join(word for _, text in sources for word in tokens(strip_comments(text))) + " "
    )
    mismatches, checked = [], 0
    for path, text in texts:
        words = tokens(text)
        if not words:
            continue
        checked += 1
        if " " + " ".join(words) + " " not in haystack:
            mismatches.append({"path": path, "text": text[:300]})
    return {
        "status": "mismatch" if mismatches else "consistent",
        "reason": (
            f"{len(mismatches)} of {checked} structured text values do not appear in the .tex source."
            if mismatches
            else f"All {checked} structured text values appear in the .tex source."
        ),
        "checked": checked,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:MAX_REPORTED],
    }
