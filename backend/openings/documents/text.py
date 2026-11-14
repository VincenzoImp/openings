"""Readable text of a revision's TeX source, derived without a TeX runtime.

A CV or letter revision is its uploaded source and PDF. Review, search and the
comparison between revisions read the text derived here from the source, as a
reader sees it in the PDF: the document body, with the macros the source defines
expanded, the commands of CV and letter classes printed as they print
(``latex.py``: moderncv entries and title, letter openings and closings, link
text), comments, settings and markup removed, accents composed, and the breaks
TeX makes (paragraphs, ``\\\\``, items, headings, environments) kept as lines.
An unknown command contributes the text of its arguments, not its options. The
same input always gives the same text, so the stored text can be checked
against its source at any time.
"""

from __future__ import annotations

import re
import unicodedata

from .latex import (
    LINE,
    PARAGRAPH,
    Context,
    collect,
    document_class,
    drop_environment_arguments,
    group_end,
    render,
)

TEX_MEDIA_TYPES = {"application/x-tex", "text/x-tex", "application/x-latex", "text/x-latex"}
IGNORED_TOKENS = {"http", "https", "www", "mailto"}

# Letters written as commands, as the characters they stand for.
_LETTERS = {"i": "i", "j": "j", "ss": "ß", "o": "ø", "O": "Ø", "l": "ł", "L": "Ł"}
_LETTERS.update({"ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ", "aa": "å", "AA": "Å"})
# Accent commands as combining marks, composed with their letter afterwards.
_ACCENTS = {
    "'": "\u0301",
    "`": "\u0300",
    "^": "\u0302",
    '"': "\u0308",
    "~": "\u0303",
    "=": "\u0304",
    ".": "\u0307",
    "c": "\u0327",
    "v": "\u030c",
    "u": "\u0306",
    "H": "\u030b",
    "k": "\u0328",
    "r": "\u030a",
    "b": "\u0331",
    "d": "\u0323",
}
_FOLD = str.maketrans(
    {"ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ł": "l", "Ł": "L"}
)
# Commands whose arguments are settings rather than visible text, by argument count.
_LAYOUT = {
    1: "vspace|hspace|includegraphics|label|ref|pageref|eqref|cite|color|pagecolor|linespread"
    "|usepackage|documentclass|geometry|hypersetup|pagestyle|thispagestyle|newgeometry"
    "|textcolor|colorbox|raisebox|input|include|setmainfont|setsansfont|setmonofont"
    "|moderncvstyle|moderncvcolor|moderncvicons|hyphenation|setlist|faIcon|addvspace"
    "|enlargethispage|stepcounter",
    2: "setlength|addtolength|setcounter|addtocounter|fontsize|rule|multicolumn",
    3: "definecolor",
    4: "titlespacing",
}
# A TeX dimension or glue: -2pt, 0pt plus .4pt minus 1fil, 0.5\baselineskip.
_NUMBER = r"[-+]?\s*(?:\d+(?:[.,]\d*)?|[.,]\d+)"
_UNIT = r"(?:pt|pc|in|bp|cm|mm|dd|cc|nd|nc|sp|em|ex|mu|px|fil{1,3}|\\[A-Za-z@]+)(?![A-Za-z])"
_DIMENSION = rf"{_NUMBER}\s*(?:true\s*)?{_UNIT}"
_GLUE = rf"{_DIMENSION}(?:\s*plus\s*{_DIMENSION})?(?:\s*minus\s*{_DIMENSION})?"
# Spacing primitives and length registers whose unbraced value is glue, not text.
_SPACING = re.compile(
    r"\\(?:kern|mkern|hskip|vskip|mskip|moveleft|moveright|raise|lower"
    r"|(?:item|par|top|partop|column|tabcol|label|arraycol|fbox)sep"
    r"|parskip|parindent|baselineskip|lineskip|leftmargin|rightmargin|itemindent"
    r"|labelwidth|hangindent|leftskip|rightskip|parfillskip|topskip|emergencystretch"
    r"|abovedisplayskip|belowdisplayskip|textwidth|linewidth|columnwidth|fboxrule)"
    rf"(?![A-Za-z@])\s*=?\s*(?:{_GLUE})?"
)
# A length set with its register unbraced: \setlength\itemsep{0pt plus .4pt}.
_ASSIGN = re.compile(r"\\(?:setlength|addtolength)\*?\s*(?:\\[A-Za-z@]+|\{[^{}]*\})\s*\{[^{}]*\}")
# Ligatures a PDF's text layer keeps (U+FB00-FB06), as the letters they join.
_LIGATURES = {code: unicodedata.normalize("NFKC", chr(code)) for code in range(0xFB00, 0xFB07)}
_ENVIRONMENT_ARGUMENTS = {
    1: "tabular|minipage|multicols|longtable|array|wrapfigure",
    2: "tabularx|tabular\\*",
}
_OPTIONAL = r"(?:\s*\[[^\]]*\])?"
_ARGUMENT = r"(?:\s*\{[^{}]*\})"
# Markers for the breaks kept as lines while the markup is removed.
_LINE, _PARAGRAPH = LINE, PARAGRAPH
# A tilde the source prints, kept apart from ~, the unbreakable space.
TILDE = "\x03"
_HEADINGS = "part|chapter|section|subsection|subsubsection|paragraph|subparagraph"
_DEFINE = re.compile(
    r"\\(?:newcommand|renewcommand|providecommand|DeclareRobustCommand)\*?\s*"
    r"(?:\{\s*\\([A-Za-z@]+)\s*\}|\\([A-Za-z@]+))\s*(?:\[(\d)\])?\s*(?:\[([^\]]*)\])?\s*(?=\{)"
    r"|\\[gex]?def\s*\\([A-Za-z@]+)((?:#\d)*)\s*(?=\{)"
)
_ENVIRONMENT_DEFINITION = re.compile(
    r"\\(?:new|renew)environment\*?\s*\{[^{}]*\}\s*(?:\[\d\])?\s*(?:\[[^\]]*\])?\s*(?=\{)"
)
_EXPANSION_PASSES = 8


def plain_letters(text: str) -> str:
    """Text with typographic ligatures (ff, fi, fl, ffi, ffl, long st, st) as their letters."""
    return text.translate(_LIGATURES)


def is_tex_source(name: str, media_type: str) -> bool:
    """Whether an uploaded file is a TeX source, by its name or media type."""
    lowered = name.lower()
    return lowered.endswith((".tex", ".ltx")) or media_type.split(";", 1)[0] in TEX_MEDIA_TYPES


def strip_comments(source: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in source.splitlines())


def _strip_markup(text: str, *, readable: bool = False) -> str:
    text = re.sub(
        r"\\(ss|ae|AE|oe|OE|aa|AA|i|j|o|O|l|L)(?![A-Za-z])\s*(?:\{\})?",
        lambda match: _LETTERS[match.group(1)],
        text,
    )
    text = re.sub(
        r"\\([cvuHkrbd])\s*\{\s*([A-Za-z])\s*\}",
        lambda match: match.group(2) + _ACCENTS[match.group(1)],
        text,
    )
    text = re.sub(
        r"\\(['\"^`~=.])\s*\{\s*([A-Za-z])\s*\}",
        lambda match: match.group(2) + _ACCENTS[match.group(1)],
        text,
    )
    text = re.sub(
        r"\\(['\"^`~=.])([A-Za-z])", lambda match: match.group(2) + _ACCENTS[match.group(1)], text
    )
    text = text.replace("\\-", "").replace("\\/", "").replace("\\@", "")
    text = re.sub(r"\\[,;:!> ]", " ", text)
    text = re.sub(r"\\\\\*?" + _OPTIONAL, " ", text)
    text = _ASSIGN.sub(" ", text)
    text = _SPACING.sub(" ", text)
    for count, names in sorted(_ENVIRONMENT_ARGUMENTS.items(), reverse=True):
        text = re.sub(rf"\\begin\s*\{{(?:{names})\}}{_OPTIONAL}{_ARGUMENT}{{{count}}}", " ", text)
    text = re.sub(r"\\(?:begin|end)\s*\{[^{}]*\}" + _OPTIONAL, " ", text)
    for count, names in sorted(_LAYOUT.items(), reverse=True):
        text = re.sub(rf"\\(?:{names})\*?(?![A-Za-z]){_OPTIONAL}{_ARGUMENT}{{{count}}}", " ", text)
    # A command the reader does not see; in readable text its options go with it.
    text = re.sub(r"\\[A-Za-z@]+\*?" + (r"(?:\s*\[[^\]]*\])*" if readable else ""), " ", text)
    # Groups only delimit: adjacent arguments read as separate words.
    text = re.sub(r"(?<!\\)\}\s*\{", " ", text)
    text = re.sub(r"(?<!\\)[{}$]", "", text)
    text = re.sub(r"\\(.)", r"\1", text)
    return unicodedata.normalize("NFC", text.replace("~", " "))


def tokens(text: str, *, markup: bool = True) -> list[str]:
    """Normalize text to comparable words, ignoring case, accents and punctuation."""
    if markup:
        text = _strip_markup(text)
    text = unicodedata.normalize("NFKD", text.translate(_FOLD))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return [
        token for token in re.findall(r"[^\W_]+", text.casefold()) if token not in IGNORED_TOKENS
    ]


def _group_end(text: str, start: int) -> int:
    """The index after the balanced group opening at ``text[start] == "{"``; -1 if open."""
    return group_end(text, start)


def _definitions(text: str) -> tuple[dict[str, tuple[int, str | None, str]], str]:
    """Macros the source defines, and the text with their definitions removed."""
    macros: dict[str, tuple[int, str | None, str]] = {}
    kept, position = [], 0
    while True:
        match = _DEFINE.search(text, position) or None
        environment = _ENVIRONMENT_DEFINITION.search(text, position)
        if environment and (not match or environment.start() < match.start()):
            end = _group_end(text, environment.end())
            if end < 0:
                break
            after = re.match(r"\s*\{", text[end:])
            if after:
                closing = _group_end(text, end + after.end() - 1)
                end = closing if closing > 0 else end
            kept.append(text[position : environment.start()])
            position = end
            continue
        if not match:
            break
        end = _group_end(text, match.end())
        if end < 0:
            break
        body = text[match.end() + 1 : end - 1]
        if match.group(5):
            macros[match.group(5)] = (len(match.group(6)) // 2, None, body)
        else:
            count = int(match.group(3) or 0)
            macros[match.group(1) or match.group(2)] = (count, match.group(4), body)
        kept.append(text[position : match.start()])
        position = end
    kept.append(text[position:])
    return macros, "".join(kept)


def _fill(body: str, arguments: list[str]) -> str:
    """A macro body with its parameters #1..#9 replaced by the call's arguments."""

    def argument(found):
        number = int(found.group(1))
        return arguments[number - 1] if 0 < number <= len(arguments) else ""

    return re.sub(r"#(\d)", argument, body)


def _expand(text: str, macros: dict[str, tuple[int, str | None, str]]) -> str:
    """Expand the source's own macros, a bounded number of times."""
    if not macros:
        return text
    pattern = re.compile(
        r"\\(" + "|".join(re.escape(name) for name in sorted(macros, key=len, reverse=True)) + r")"
        r"(?![A-Za-z@])"
    )
    limit = max(len(text) * 4, 200_000)
    for _ in range(_EXPANSION_PASSES):
        pieces, position, changed = [], 0, False
        for match in pattern.finditer(text):
            if match.start() < position:
                continue
            count, default, body = macros[match.group(1)]
            index, arguments = match.end(), []
            if default is not None:
                optional = re.match(r"\s*\[([^\]]*)\]", text[index:])
                arguments.append(optional.group(1) if optional else default)
                if optional:
                    index += optional.end()
            while len(arguments) < count:
                opening = re.match(r"\s*\{", text[index:])
                if not opening:
                    break
                end = _group_end(text, index + opening.end() - 1)
                if end < 0:
                    break
                arguments.append(text[index + opening.end() : end - 1])
                index = end
            if len(arguments) < count:
                continue
            pieces.append(text[position : match.start()] + "{" + _fill(body, arguments) + "}")
            position, changed = index, True
        if not changed:
            break
        pieces.append(text[position:])
        expanded = "".join(pieces)
        if len(expanded) > limit:
            break
        text = expanded
    return text


def _breaks(text: str) -> str:
    """Mark where TeX breaks lines and paragraphs; other newlines are spaces."""
    text = re.sub(r"\n[ \t]*\n\s*", _PARAGRAPH, text).replace("\n", " ")
    text = re.sub(r"\\\\\*?(?:\s*\[[^\]]*\])?", _LINE, text)
    text = re.sub(r"\\(?:newline|linebreak)(?![A-Za-z])", _LINE, text)
    text = re.sub(r"\\(?:par|smallskip|medskip|bigskip)(?![A-Za-z])", _PARAGRAPH, text)
    text = re.sub(
        r"\\item(?![A-Za-z])\s*(?:\[([^\]]*)\])?",
        lambda match: _LINE + "• " + (match.group(1) + " " if match.group(1) else ""),
        text,
    )
    text = re.sub(r"\\(begin|end)(?![A-Za-z])", _LINE + r"\\\1", text)
    pieces, position = [], 0
    for match in re.finditer(
        rf"\\(?:{_HEADINGS})\*?(?![A-Za-z])\s*(?:\[[^\]]*\])?\s*(?=\{{)", text
    ):
        if match.start() < position:
            continue
        end = _group_end(text, match.end())
        if end < 0:
            continue
        pieces.append(text[position : match.start()])
        pieces.append(_PARAGRAPH + text[match.end() : end] + _LINE)
        position = end
    pieces.append(text[position:])
    text = "".join(pieces)
    # Table cells and \hfill separate words; math delimiters are not text.
    return re.sub(r"(?<!\\)&|\\hfill(?![A-Za-z])", " ", text)


def _tidy(text: str) -> str:
    text = text.replace("---", "—").replace("--", "–").replace("``", "“").replace("''", "”")
    text = text.replace(TILDE, "~")
    paragraphs = []
    for paragraph in text.split(_PARAGRAPH):
        lines = [" ".join(line.split()) for line in paragraph.split(_LINE)]
        lines = [line for line in lines if line]
        if lines:
            paragraphs.append("\n".join(lines))
    return "\n\n".join(paragraphs)


def derive_text(source: str) -> str:
    """The readable text of one TeX source: its body, without markup."""
    text = strip_comments(source)
    preamble, body = "", text
    begin = re.search(r"\\begin\s*\{document\}", text)
    if begin:
        preamble, body = text[: begin.start()], text[begin.end() :]
        end = re.search(r"\\end\s*\{document\}", body)
        if end:
            body = body[: end.start()]
    macros, preamble = _definitions(preamble)
    own, body = _definitions(body)
    macros.update(own)
    context = Context(document_class(text))
    body = _expand(body, macros)
    # Personal data set in the preamble is printed where the body asks for it.
    collect(_expand(preamble, macros) + "\n" + body, context)
    body = render(drop_environment_arguments(body), context)
    return plain_letters(_tidy(_strip_markup(_breaks(body), readable=True)))


def revision_text(sources: list[tuple[str, str]]) -> str | None:
    """The derived text of a revision's sources (name, text), in name order; None without one."""
    if not sources:
        return None
    return "\n\n".join(
        text for text in (derive_text(source) for _, source in sorted(sources)) if text
    )


def decode_source(data: bytes) -> str:
    """A stored source as text; bytes that are not UTF-8 are replaced."""
    return data.decode("utf-8", "replace")
