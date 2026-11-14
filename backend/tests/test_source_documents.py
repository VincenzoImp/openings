"""A CV or letter revision's TeX source and the PDF built from it; text derived from the source."""

import hashlib
import re
from pathlib import Path

import pytest

from document_fixtures import PDF, SOURCE, TEXT, tex, text_pdf, upload
from openings.documents import DocumentCreate, UploadReservation
from openings.documents.pdf import pdf_text
from openings.documents.text import derive_text, revision_text, tokens
from openings.errors import DomainError

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def sha(data):
    return hashlib.sha256(data).hexdigest()


# A moderncv CV: personal data in the preamble, printed by \\makecvtitle; entries
# printed in columns; the source's own macro around \\cvitem.
MODERNCV = r"""\documentclass[11pt,a4paper,sans]{moderncv}
\moderncvstyle{classic}
\moderncvcolor{blue}
\usepackage[utf8]{inputenc}
\usepackage[scale=0.82]{geometry}
\name{Alex}{Example}
\title{Backend Engineer}
\address{Example Street 1}{8000 Zurich}{Switzerland}
\phone[mobile]{+41~00~000~00~00}
\email{alex@example.test}
\homepage{example.test}
\social[linkedin]{alex-example}
\social[github]{alexexample}
\extrainfo{Swiss work permit}
\newcommand{\skill}[2]{\cvitem{#1}{#2}}
\begin{document}
\makecvtitle
\section{Experience}
\cventry{2021--present}{Backend Engineer}{Example Cloud}{Zurich}{}{%
\begin{itemize}
\item Reduced API p95 latency by 20\% through tracing and caching.
\item Built \textbf{Python} services for M\"{u}ller \& Co.~AG.
\end{itemize}}
\cventry[2pt]{2018--2021}{Software Engineer}{Sample Grid}{Basel}{\textit{Grade: A}}{Migrated 40 services to Kubernetes.}
\section{Education}
\cventry{2014--2018}{MSc Computer Science}{ETH Zurich}{Zurich}{GPA 5.5/6}{}
\section{Skills}
\skill{Languages}{Python, Go, SQL}
\cvitemwithcomment{German}{C1}{Goethe certificate}
\cvdoubleitem{Cloud}{AWS, GCP}{Tools}{Docker, Terraform}
\cvlistitem{Open-source maintainer of \href{https://example.test/tool}{a tracing tool}}
\cvlistdoubleitem{Running}{Chess}
\section{Links}
\cvitem{Web}{\url{https://example.test}}
\end{document}
"""
MODERNCV_TEXT = """Alex Example
Backend Engineer
Example Street 1, 8000 Zurich, Switzerland
+41 00 000 00 00
alex@example.test
example.test
alex-example
alexexample
Swiss work permit

Experience
2021–present Backend Engineer, Example Cloud, Zurich
• Reduced API p95 latency by 20% through tracing and caching.
• Built Python services for Müller & Co. AG.
2018–2021 Software Engineer, Sample Grid, Basel, Grade: A
Migrated 40 services to Kubernetes.

Education
2014–2018 MSc Computer Science, ETH Zurich, Zurich, GPA 5.5/6

Skills
Languages: Python, Go, SQL
German: C1, Goethe certificate
Cloud: AWS, GCP
Tools: Docker, Terraform
• Open-source maintainer of a tracing tool
• Running
• Chess

Links
Web: https://example.test"""
MODERNCV_LETTER = r"""\documentclass[11pt,a4paper]{moderncv}
\moderncvstyle{classic}
\name{Alex}{Example}
\address{Example Street 1}{8000 Zurich}
\email{alex@example.test}
\begin{document}
\recipient{Hiring Team}{Example Labs\\Main Street 5\\8001 Zurich}
\date{13 November 2026}
\opening{Dear Hiring Team,}
\closing{Kind regards,}
\enclosure[Attached]{CV}
\makelettertitle
I build reliable Python services and would like to bring that work to Example Labs.

My work at Example Cloud reduced latency by 20\%.
\makeletterclosing
\end{document}
"""
KOMA = r"""\documentclass[version=last]{scrlttr2}
\setkomavar{fromname}{Alex Example}
\setkomavar{fromaddress}{Example Street 1\\8000 Zurich}
\setkomavar{fromemail}{alex@example.test}
\setkomavar{subject}{Application as Backend Engineer}
\begin{document}
\begin{letter}{Example Labs\\Main Street 5\\8001 Zurich}
\opening{Dear Hiring Team,}
I build reliable Python services --- and measure them.
\closing{Kind regards,}
\end{letter}
\end{document}
"""
CUSTOM = r"""\documentclass[10pt]{article}
\usepackage{fontawesome5}
\newcommand{\entry}[4]{\textbf{#1} \hfill #2 \\ \textit{#3} \hfill #4}
\newcommand{\contact}[2]{\faIcon{#1}~#2}
\begin{document}
\begin{center}
{\Huge\scshape Alex Example}\\[4pt]
\contact{envelope}{\href{mailto:alex@example.test}{alex@example.test}} $|$
\contact{phone}{+41 00 000 00 00} \textbar{} \faLinkedin\ \href{https://linkedin.com/in/x}{alex-example}
\end{center}
\section*{Experience}
\entry{Backend Engineer}{2021 -- present}{Example Cloud}{Zurich}
\begin{itemize}[leftmargin=*,noitemsep]
  \item Reduced latency by 20\% ($\sim$40\,ms) via caching.
\end{itemize}
\begin{tabular}{@{}ll}
\textbf{Languages} & English (C2), German (C1) \\
\textbf{Tools} & Docker, Terraform
\end{tabular}
\end{document}
"""


def test_derived_text_reads_as_the_pdf_prints_it():
    assert derive_text(MODERNCV) == MODERNCV_TEXT
    letter = derive_text(MODERNCV_LETTER)
    assert letter.startswith("Alex Example\nExample Street 1, 8000 Zurich\nalex@example.test\n\n")
    assert "Hiring Team\nExample Labs\nMain Street 5\n8001 Zurich\n\n13 November 2026" in letter
    assert letter.endswith("Kind regards,\n\nAlex Example\nCV")
    koma = derive_text(KOMA)
    assert "Alex Example\nExample Street 1\n8000 Zurich\nalex@example.test" in koma
    assert "Application as Backend Engineer\n\nDear Hiring Team," in koma
    assert koma.endswith("Kind regards,\n\nAlex Example")
    custom = derive_text(CUSTOM)
    # Icons, column specifications and options are not text; link text is.
    assert "alex@example.test | +41 00 000 00 00 | alex-example" in custom
    assert "• Reduced latency by 20% (~40 ms) via caching." in custom
    assert custom.endswith("Languages English (C2), German (C1)\nTools Docker, Terraform")
    # The text is the body without markup, with the breaks TeX makes.
    assert derive_text(SOURCE) == TEXT
    # The preamble and comments are not text; a fragment without a body is read whole.
    assert derive_text("% only a comment\nPlain \\emph{fragment}.") == "Plain fragment."
    assert derive_text("\\def\\who#1{Dr.~#1}\\who{Example}") == "Dr. Example"
    # Recursive macros stop after a bounded number of expansions.
    assert len(derive_text("\\newcommand{\\loop}{a\\loop}\\loop")) < 100
    assert revision_text([]) is None
    assert revision_text([("b.tex", "Second."), ("a.tex", "First.")]) == "First.\n\nSecond."
    assert tokens(r"Stra\ss e \v{S}koda na\"{\i}ve") == ["strasse", "skoda", "naive"]


GLUE = r"""\documentclass{article}
\begin{document}
\section*{Experience}\vspace{-2pt plus 1pt}
\begin{itemize}\setlength\itemsep{0pt plus .4pt}\itemsep=0pt plus .4pt
  \item Of\-fice work, efﬁcient ﬂows\vskip 2pt plus 1pt minus 1pt
  \item Kerned\kern-.5em text\hspace*{\fill}end \parskip 0pt plus .4pt
\end{itemize}
\setlength{\parskip}{0.5\baselineskip plus 2pt}\addvspace{4pt plus 2pt}
\titlespacing*{\section}{0pt}{8pt plus 2pt}{4pt}
Done in 2021 with 3 people.
\end{document}
"""


def test_derived_text_has_no_spacing_glue_or_ligatures_and_templates_build_anywhere():
    # Lengths and glue of spacing commands are layout, not text; numbers in text stay.
    assert derive_text(GLUE) == (
        "Experience\n• Office work, efficient flows\n• Kerned text end\nDone in 2021 with 3 people."
    )
    # A PDF's text layer gives ligatures (here StandardEncoding's fi and fl) as letters.
    assert pdf_text(text_pdf("e\xaecient \xafows")) == "eficient flows"
    for name in ("cv.tex", "letter.tex"):
        source = (EXAMPLES / name).read_text()
        text = derive_text(source)
        assert text.startswith("Alex Example\n") and "pt" not in text.split()
        assert not re.search(r"\b(?:plus|minus)\b|\d(?:pt|em)\b|[\ufb00-\ufb06]", text)
        # pdfTeX-only primitives are guarded, so pdflatex and Tectonic (XeTeX) both build.
        guarded = re.sub(r"\\ifpdftex\b.*?\\fi\b", "", source, flags=re.DOTALL)
        assert "\\ifpdftex" in source
        assert not re.search(r"glyphtounicode|\\pdf[a-z]+", guarded), name


def reserve(client, document_id, name, data, media_type, source_sha256=None):
    value = {
        "owner_type": "document",
        "owner_id": document_id,
        "name": name,
        "media_type": media_type,
        "size": len(data),
    }
    if source_sha256:
        value["source_sha256"] = source_sha256
    return client.post("/api/v1/files/uploads", json=value)


def send(client, document_id, name, data, media_type, source_sha256=None):
    grant = reserve(client, document_id, name, data, media_type, source_sha256)
    assert grant.status_code == 201, grant.text
    grant = grant.json()
    return client.put(grant["url"], headers=grant["headers"], content=data)


def code(response):
    return response.status_code, response.json()["error"]["code"]


def test_a_cv_is_its_source_and_the_pdf_built_from_it(app, client):
    workspace = app.state.workspace
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build services."})
    application = workspace.create_application({"job_id": job["id"]})
    refused = client.post(
        "/api/v1/documents",
        json={
            "application_id": application["id"],
            "kind": "cv",
            "content": {"text": "CV"},
            "pdf": {"name": "cv.pdf", "size": len(PDF)},
        },
    )
    assert code(refused) == (422, "content_not_accepted")
    created = client.post(
        "/api/v1/documents",
        json={
            "application_id": application["id"],
            "title": "CV",
            "note": "First draft.",
            "pdf": {"name": "cv.pdf", "size": len(PDF)},
        },
    )
    assert created.status_code == 201
    cv = created.json()
    assert "content" not in cv and cv["text"] is None
    assert (cv["note"], cv["highlight_ids"], cv["career_ids"]) == ("First draft.", [], [])

    # A PDF naming a source comes after that source.
    source = SOURCE.encode()
    assert code(reserve(client, cv["id"], "cv.pdf", PDF, "application/pdf", sha(source))) == (
        409,
        "source_required",
    )
    assert code(send(client, cv["id"], "cv.tex", b"caf\xe9", "application/x-tex")) == (
        422,
        "source_encoding",
    )
    assert send(client, cv["id"], "cv.tex", source, "application/x-tex").status_code == 200
    read = client.get(f"/api/v1/documents/{cv['id']}").json()
    assert (read["text"], read["source_sha256"]) == (TEXT, sha(source))
    assert code(reserve(client, cv["id"], "other.tex", b"x", "application/x-tex")) == (
        409,
        "source_exists",
    )
    other = sha(b"another source")
    assert code(reserve(client, cv["id"], "cv.pdf", PDF, "application/pdf", other)) == (
        409,
        "source_mismatch",
    )
    assert code(
        reserve(client, cv["id"], "cv.pdf", PDF, "application/octet-stream", sha(source))
    ) == (
        422,
        "pdf_media_type",
    )
    assert code(reserve(client, cv["id"], "photo.png", b"png", "image/png", sha(source))) == (
        422,
        "source_sha256",
    )
    # With a source, the PDF must name it.
    assert code(reserve(client, cv["id"], "cv.pdf", PDF, "application/pdf")) == (
        422,
        "source_sha256_required",
    )
    assert client.get(f"/api/v1/documents/{cv['id']}").json()["complete"] is False
    pdf = send(client, cv["id"], "cv.pdf", PDF, "application/pdf", sha(source)).json()
    assert pdf["source_sha256"] == sha(source)
    # Complete once its PDF is stored, and immutable: a change is a new revision.
    assert code(reserve(client, cv["id"], "copy.pdf", PDF, "application/pdf", sha(source))) == (
        409,
        "revision_complete",
    )
    complete = client.get(f"/api/v1/documents/{cv['id']}").json()
    assert complete["complete"] is True
    # The text stays the one derived from the TeX source.
    assert (complete["text"], complete["text_from"]) == (TEXT, "tex")

    # A new revision is compared with the one it replaces, line by line.
    revised = client.post(
        "/api/v1/documents",
        json={
            "application_id": application["id"],
            "title": "CV",
            "previous_id": cv["id"],
            "pdf": {"name": "cv.pdf", "size": len(PDF)},
        },
    ).json()
    changed = SOURCE.replace("Python, SQL.", "Python, SQL, Rust.").encode()
    assert send(client, revised["id"], "cv.tex", changed, "application/x-tex").status_code == 200
    comparison = client.get(f"/api/v1/documents/{revised['id']}/comparison").json()
    assert (comparison["other_id"], comparison["added"], comparison["removed"]) == (cv["id"], 1, 1)
    assert [line for line in comparison["lines"] if line["change"] != "same"] == [
        {"change": "removed", "text": "Skills: Python, SQL."},
        {"change": "added", "text": "Skills: Python, SQL, Rust."},
    ]
    assert comparison["text"] == {"document": True, "other": True}
    backwards = client.get(
        f"/api/v1/documents/{cv['id']}/comparison", params={"other_id": revised["id"]}
    ).json()
    assert (backwards["added"], backwards["removed"]) == (1, 1)
    assert code(client.get(f"/api/v1/documents/{cv['id']}/comparison")) == (
        422,
        "comparison_target",
    )
    # The derived text is searched with titles and notes.
    found = client.get("/api/v1/documents", params={"q": "Rust"}).json()
    assert [item["id"] for item in found["items"]] == [revised["id"]]
    assert client.get("/api/v1/documents", params={"q": "First draft"}).json()["total"] == 1


def test_form_answers_keep_structured_content_and_compare_it(app):
    workspace, documents = app.state.workspace, app.state.documents
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build services."})
    application = workspace.create_application({"job_id": job["id"]})
    first = documents.create_document(
        DocumentCreate(
            application_id=application["id"],
            kind="answers",
            content={"answers": {"why": "Reliable services."}},
        )
    )
    assert first["content"] == {"answers": {"why": "Reliable services."}}
    assert first["complete"] is True
    second = documents.create_document(
        DocumentCreate(
            application_id=application["id"],
            kind="answers",
            previous_id=first["id"],
            content={"answers": {"why": "Reliable data services."}},
        )
    )
    comparison = documents.compare_documents(second["id"])
    assert [line for line in comparison["lines"] if line["change"] != "same"] == [
        {"change": "removed", "text": "answers.why: Reliable services."},
        {"change": "added", "text": "answers.why: Reliable data services."},
    ]
    other = workspace.create_application(
        {"job_id": workspace.ingest_job({"title": "Other", "posting": "Other."})["id"]}
    )
    elsewhere = documents.create_document(
        DocumentCreate(application_id=other["id"], kind="answers", content={})
    )
    with pytest.raises(DomainError) as error:
        documents.compare_documents(second["id"], elsewhere["id"])
    assert error.value.code == "comparison_target"


def test_a_retry_returns_only_a_revision_without_files(app, client):
    workspace, documents = app.state.workspace, app.state.documents
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build services."})
    application = workspace.create_application({"job_id": job["id"]})
    value = DocumentCreate(
        application_id=application["id"], title="CV", pdf={"name": "cv.pdf", "size": 1}
    )
    first = documents.create_document(value)
    assert documents.create_document(value)["id"] == first["id"]
    upload(documents, client.put, first["id"], "cv.tex", tex(), "application/x-tex")
    assert documents.create_document(value)["id"] != first["id"]


def test_parallel_upload_grants_remain_valid_until_a_revision_is_complete(app, client):
    workspace, documents = app.state.workspace, app.state.documents
    job = workspace.ingest_job({"posting": "Build APIs"})
    application = workspace.create_application({"job_id": job["id"]})
    doc = documents.create_document(DocumentCreate(application_id=application["id"], kind="other"))
    grants = [
        documents.reserve_upload(
            UploadReservation(owner_type="document", owner_id=doc["id"], name=name, size=3)
        )
        for name in ("cv.tex", "cv.txt", "late.txt")
    ]
    for grant in grants[:2]:
        assert client.put(grant["url"], headers=grant["headers"], content=b"abc").status_code == 200
    current = documents.get_document(doc["id"])
    assert current["version"] == 3 and len(current["files"]) == 2
    # The identical completed transfer is a retry, not another mutation.
    assert (
        client.put(grants[0]["url"], headers=grants[0]["headers"], content=b"abc").status_code
        == 200
    )
    assert documents.get_document(doc["id"])["version"] == 3
    # A file of another kind of revision may still be added.
    assert (
        client.put(grants[2]["url"], headers=grants[2]["headers"], content=b"abc").status_code
        == 200
    )
    assert len(documents.get_document(doc["id"])["files"]) == 3
    # A CV is complete once its PDF is stored: a grant reserved before is refused.
    cv = documents.create_document(
        DocumentCreate(
            application_id=application["id"], kind="cv", pdf={"name": "cv.pdf", "size": 8}
        )
    )
    late = documents.reserve_upload(
        UploadReservation(owner_type="document", owner_id=cv["id"], name="photo.png", size=3)
    )
    pdf = cv["uploads"]["pdf"]
    assert client.put(pdf["url"], headers=pdf["headers"], content=b"%PDF-1.4").status_code == 200
    assert documents.get_document(cv["id"])["complete"]
    refused = client.put(late["url"], headers=late["headers"], content=b"abc")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "revision_complete"
    assert len(documents.get_document(cv["id"])["files"]) == 1
