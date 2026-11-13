"""What the commands of CVs and letters print, without a TeX runtime.

Classes such as moderncv keep personal data in the preamble (``\\name``,
``\\email``, ``\\address``…) and print it where the body says ``\\makecvtitle``
or ``\\makelettertitle``; entries such as ``\\cventry`` print their arguments in
columns; letters print ``\\opening`` and ``\\closing`` with the sender's details.
``render`` replaces each known command with the text a reader sees in the PDF,
with line and paragraph markers; ``text.py`` removes the remaining markup, so
an unknown command still contributes the text of its arguments.
"""

from __future__ import annotations

import re
from collections.abc import Callable

LINE, PARAGRAPH = "\x01", "\x02"


def group_end(text: str, start: int, opening: str = "{", closing: str = "}") -> int:
    """The index after the balanced group opening at ``text[start]``; -1 if it stays open."""
    depth, index = 0, start
    while index < len(text):
        character = text[index]
        if character == "\\":
            index += 2
            continue
        if character == opening:
            depth += 1
        elif character == closing:
            depth -= 1
            if depth == 0:
                return index + 1
        elif opening == "[" and character == "{":
            # Braces inside an optional argument may hold a closing bracket.
            end = group_end(text, index)
            if end < 0:
                return -1
            index = end
            continue
        index += 1
    return -1


def arguments(text: str, index: int, count: int, optional: int = 1):
    """Up to ``optional`` [..] groups, then exactly ``count`` {..} groups, from ``index``.

    Returns (optional arguments, arguments, end) or None when an argument is missing.
    """
    options: list[str] = []
    while len(options) < optional:
        found = re.match(r"\s*\[", text[index:])
        if not found:
            break
        end = group_end(text, index + found.end() - 1, "[", "]")
        if end < 0:
            break
        options.append(text[index + found.end() : end - 1])
        index = end
    values: list[str] = []
    while len(values) < count:
        found = re.match(r"\s*\{", text[index:])
        if not found:
            return None
        end = group_end(text, index + found.end() - 1)
        if end < 0:
            return None
        values.append(text[index + found.end() : end - 1])
        index = end
    return options, values, index


def _joined(values, separator=", "):
    return separator.join(value for value in values if value.strip())


def _lines(*values):
    return LINE + LINE.join(value for value in values if value.strip()) + LINE


class Context:
    """The document class and the personal data a class prints later."""

    def __init__(self, document_class: str):
        self.document_class = document_class
        self.data: dict[str, list[list[str]]] = {}

    @property
    def moderncv(self):
        return self.document_class == "moderncv"

    @property
    def koma(self):
        return self.document_class in {"scrlttr2", "scrletter"}

    def first(self, name, default=None):
        values = self.data.get(name)
        return values[0] if values else default

    def text(self, name):
        values = self.first(name)
        return _joined(values, " ") if values else ""

    def header(self):
        """The personal data a CV or letter title prints, one item per line."""
        name = self.first("name")
        full = (
            _joined(name, " ")
            if name
            else _joined([self.text("firstname"), self.text("familyname")], " ")
        )
        lines = [full, self.text("title")]
        address = self.first("address")
        if address:
            lines.append(_joined(address))
        for kind in ("phone", "mobile", "fax", "email", "homepage", "social", "extrainfo"):
            lines.extend(_joined(values, " ") for values in self.data.get(kind, []))
        lines.append(self.text("quote"))
        return _lines(*lines)

    def koma_sender(self):
        values = [self.koma_variable(name) for name in ("fromname", "fromaddress")]
        values += [self.koma_variable(name) for name in ("fromphone", "fromemail", "fromurl")]
        return _lines(*values)

    def koma_variable(self, name):
        for values in self.data.get("setkomavar", []):
            if values and values[0].strip() == name:
                return values[-1] if len(values) > 1 else ""
        return ""


# Personal data that moderncv, the letter classes and \maketitle print elsewhere:
# command -> (optional arguments, arguments).
PERSONAL = {
    "name": (0, 2),
    "firstname": (0, 1),
    "familyname": (0, 1),
    "title": (0, 1),
    "address": (0, 3),
    "phone": (1, 1),
    "mobile": (0, 1),
    "fax": (0, 1),
    "email": (0, 1),
    "homepage": (0, 1),
    "social": (1, 1),
    "extrainfo": (0, 1),
    "quote": (0, 1),
    "photo": (1, 1),
    "recipient": (0, 2),
    "date": (0, 1),
    "opening": (0, 1),
    "closing": (0, 1),
    "signature": (0, 1),
    "enclosure": (1, 1),
    "author": (0, 1),
    "setkomavar": (1, 2),
}


def parse(name: str, text: str, index: int, context: Context):
    """The arguments of a known command at ``index``, or None when they are missing."""
    optional, count = KNOWN[name][:2] if name in KNOWN else PERSONAL[name]
    if name == "address":
        # moderncv: street, city, country (the last ones may be left out); the
        # letter classes: one argument, lines separated by \\.
        for count in (3, 2, 1) if context.moderncv else (1,):
            parsed = arguments(text, index, count, optional)
            if parsed is not None:
                return parsed
        return None
    return arguments(text, index, count, optional)


def collect(text: str, context: Context):
    """Record the personal data the source sets, wherever it sets it."""
    pattern = re.compile(r"\\(" + "|".join(PERSONAL) + r")(?![A-Za-z@])\*?")
    for found in pattern.finditer(text):
        name = found.group(1)
        parsed = parse(name, text, found.end(), context)
        if parsed is None:
            continue
        options, values, _ = parsed
        if name == "setkomavar":
            values = [values[0], *options, values[1]]
        context.data.setdefault(name, []).append(values)


Renderer = Callable[[list[str], list[str], Context], str]


def _cventry(options, values, context):
    years, title, employer, city, grade, description = values
    head = _joined([title, employer, city, grade])
    return _lines(_joined([years, head], " "), description)


def _personal(name):
    """A personal-data command: printed later by moderncv and the letter classes."""

    def render(options, values, context):
        if context.moderncv or (context.koma and name == "setkomavar"):
            return ""
        if name in {"opening", "closing", "signature"} and not context.moderncv:
            return _letter(name, values, context)
        if name in {"title", "author", "date", "photo", "setkomavar", "address"}:
            # Set for \maketitle, the letter heading or the class; printed there.
            return ""
        return _joined(values, " ")

    return render


def _letter(name, values, context):
    """\\opening and \\closing of the letter classes, printed where they stand."""
    if name == "signature":
        return ""
    if name == "opening":
        sender = context.koma_sender() if context.koma else _lines(context.text("address"))
        subject = context.koma_variable("subject") if context.koma else ""
        return sender + PARAGRAPH + _lines(subject) + PARAGRAPH + values[0] + PARAGRAPH
    signature = (
        context.koma_variable("signature") or context.koma_variable("fromname")
        if context.koma
        else context.text("signature")
    )
    return PARAGRAPH + values[0] + PARAGRAPH + _lines(signature)


def _makelettertitle(options, values, context):
    recipient = context.first("recipient") or []
    return (
        context.header()
        + PARAGRAPH
        + _lines(*recipient)
        + PARAGRAPH
        + _lines(context.text("date"))
        + PARAGRAPH
        + context.text("opening")
        + PARAGRAPH
    )


def _makeletterclosing(options, values, context):
    name = context.first("name")
    full = _joined(name, " ") if name else ""
    enclosures = [_joined(values, " ") for values in context.data.get("enclosure", [])]
    return PARAGRAPH + context.text("closing") + PARAGRAPH + _lines(full, *enclosures)


def _maketitle(options, values, context):
    if context.moderncv:
        return context.header()
    return _lines(context.text("title"), context.text("author"), context.text("date"))


# Command -> (optional arguments, arguments, renderer).
KNOWN: dict[str, tuple[int, int, Renderer]] = {
    "cventry": (1, 6, _cventry),
    "cvitem": (1, 2, lambda o, v, c: _lines(_joined(v, ": "))),
    "cvitemwithcomment": (1, 3, lambda o, v, c: _lines(_joined([_joined(v[:2], ": "), v[2]]))),
    "cvdoubleitem": (
        1,
        4,
        lambda o, v, c: _lines(_joined(v[:2], ": "), _joined(v[2:], ": ")),
    ),
    "cvlistitem": (1, 1, lambda o, v, c: _lines("• " + v[0])),
    "cvlistdoubleitem": (
        1,
        2,
        lambda o, v, c: _lines("• " + v[0], "• " + v[1] if v[1].strip() else ""),
    ),
    "cvline": (1, 2, lambda o, v, c: _lines(_joined(v, ": "))),
    "cvcolumn": (1, 2, lambda o, v, c: _lines(*v)),
    "makecvtitle": (0, 0, _maketitle),
    "maketitle": (0, 0, _maketitle),
    "makelettertitle": (0, 0, _makelettertitle),
    "makeletterclosing": (0, 0, _makeletterclosing),
    "href": (0, 2, lambda o, v, c: v[1]),
    "url": (0, 1, lambda o, v, c: v[0]),
    "nolinkurl": (0, 1, lambda o, v, c: v[0]),
    "parbox": (1, 2, lambda o, v, c: v[1]),
    "makebox": (2, 1, lambda o, v, c: v[0]),
    "footnote": (1, 1, lambda o, v, c: " " + v[0]),
    "faIcon": (1, 1, lambda o, v, c: ""),
    "ps": (0, 1, lambda o, v, c: _lines(v[0])),
    "encl": (0, 1, lambda o, v, c: _lines(v[0])),
    "cc": (0, 1, lambda o, v, c: _lines(v[0])),
    **{name: (*PERSONAL[name], _personal(name)) for name in PERSONAL},
}

# Commands that print a character or a word.
SYMBOLS = {
    "textbar": "|",
    "textbullet": "•",
    "cdot": "·",
    "textperiodcentered": "·",
    "ldots": "…",
    "dots": "…",
    "textellipsis": "…",
    "textendash": "–",
    "textemdash": "—",
    "textquoteright": "’",
    "textquoteleft": "‘",
    "textquotedblleft": "“",
    "textquotedblright": "”",
    "euro": "€",
    "texteuro": "€",
    "pounds": "£",
    "textsterling": "£",
    "textdollar": "$",
    "LaTeX": "LaTeX",
    "TeX": "TeX",
    "textasciitilde": "\x03",
    "textbackslash": "\\",
    "slash": "/",
    "textunderscore": "_",
    "copyright": "©",
    "textcopyright": "©",
    "textregistered": "®",
    "texttrademark": "™",
    "textdegree": "°",
    "times": "×",
    "sim": "\x03",
    "approx": "≈",
    "pm": "±",
    "geq": "≥",
    "leq": "≤",
    "rightarrow": "→",
    "to": "→",
    "textgreater": ">",
    "textless": "<",
    "quad": " ",
    "qquad": " ",
}
_KNOWN = re.compile(
    r"(?<!\\)\\("
    + "|".join(sorted(map(re.escape, KNOWN), key=len, reverse=True))
    + r")(?![A-Za-z@])\*?"
)
_SYMBOL = re.compile(
    r"(?<!\\)\\("
    + "|".join(sorted(map(re.escape, SYMBOLS), key=len, reverse=True))
    + r")(?![A-Za-z@])\s*(?:\{\})?"
)


def document_class(text: str) -> str:
    found = re.search(r"\\documentclass\s*(?:\[[^\]]*\])?\s*\{\s*([^{}\s]+)\s*\}", text)
    return found.group(1) if found else ""


def render(text: str, context: Context, depth: int = 0) -> str:
    """Replace each known command, its arguments rendered first, with what it prints."""
    if depth > 6:
        return text
    pieces, index = [], 0
    while found := _KNOWN.search(text, index):
        renderer = KNOWN[found.group(1)][2]
        parsed = parse(found.group(1), text, found.end(), context)
        if parsed is None:
            pieces.append(text[index : found.end()])
            index = found.end()
            continue
        options, values, end = parsed
        values = [render(value, context, depth + 1) for value in values]
        pieces.append(text[index : found.start()])
        pieces.append("{" + renderer(options, values, context) + "}")
        index = end
    pieces.append(text[index:])
    return _SYMBOL.sub(lambda found: SYMBOLS[found.group(1)], "".join(pieces))


# Environments whose arguments are layout (column specifications, widths), by count.
ENVIRONMENT_ARGUMENTS = {
    "tabular": 1,
    "tabular*": 2,
    "tabularx": 2,
    "tabulary": 2,
    "longtable": 1,
    "array": 1,
    "minipage": 1,
    "multicols": 1,
    "wrapfigure": 2,
    "paracol": 1,
}
_BEGIN = re.compile(r"\\begin\s*\{(" + "|".join(map(re.escape, ENVIRONMENT_ARGUMENTS)) + r")\}")


def drop_environment_arguments(text: str) -> str:
    """Remove the layout arguments of tables and boxes, nested braces included."""
    pieces, index = [], 0
    while found := _BEGIN.search(text, index):
        parsed = arguments(text, found.end(), ENVIRONMENT_ARGUMENTS[found.group(1)], 2)
        pieces.append(text[index : found.end()])
        index = parsed[2] if parsed else found.end()
    pieces.append(text[index:])
    return "".join(pieces)
