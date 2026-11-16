"""The demo's documents follow the demo's own writing rules, and its PDFs are built
from the TeX beside them."""

import re
import unicodedata
from io import BytesIO

from pypdf import PdfReader

from openings.demo import seed_demo
from openings.demo.jobs import FILES

LETTERS = ("demo-letter", "demo-letter-meridian", "demo-letter-fernhill")
TEX = ("demo-cv", *LETTERS)


def letter_body(name):
    tex = (FILES / f"{name}.tex").read_text()
    return re.search(r"Dear Hiring Team,\n\n(.*?)\n\nKind regards", tex, re.DOTALL)[1]


def words(text):
    return re.findall(r"[a-z0-9']+", text.lower().replace("\\%", "%"))


def plain(text):
    """Letters and digits only: what survives line breaks and hyphenation in a PDF."""
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", text).lower())


def test_each_demo_letter_has_three_paragraphs_under_200_words_and_no_gap():
    for name in LETTERS:
        body = letter_body(name)
        assert len(body.split("\n\n")) == 3, name
        assert len(words(body)) < 200, name
        assert "I have not" not in body, name


def test_the_committed_pdfs_match_their_tex():
    for name in TEX:
        tex = (FILES / f"{name}.tex").read_text()
        reader = PdfReader(BytesIO((FILES / f"{name}.pdf").read_bytes()))
        assert len(reader.pages) == 1, name
        pdf = plain("".join(page.extract_text() for page in reader.pages))
        if name in LETTERS:
            parts = letter_body(name).split("\n\n")
        else:
            parts = re.findall(r"\\item (.*?)(?=\n\s*\\item|\n\\end)", tex, re.DOTALL)
        assert parts, name
        for part in parts:
            assert plain(part.replace("\\%", "%")) in pdf, (name, part)


def test_hidden_highlights_appear_in_no_document_and_freightwise_has_a_brief(app):
    seed_demo(app)
    db = app.state.workspace.db
    runs = set()
    for name in TEX:
        tokens = words((FILES / f"{name}.tex").read_text())
        runs |= {tuple(tokens[i : i + 5]) for i in range(len(tokens) - 4)}
    hidden = db.all("SELECT text FROM claims WHERE NOT approved")
    assert hidden
    for row in hidden:
        tokens = words(row["text"])
        assert not {tuple(tokens[i : i + 5]) for i in range(len(tokens) - 4)} & runs, row["text"]
    briefs = db.all(
        "SELECT n.body FROM notes n JOIN jobs j ON j.id=n.job_id WHERE j.company='Freightwise' "
        "AND n.author='agent:Claude Code' AND n.pinned_at IS NULL"
    )
    assert any(row["body"].startswith("Interview brief:") for row in briefs)
