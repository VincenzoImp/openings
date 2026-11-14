"""CV and letter revisions as their source and PDF, and an application's guidance."""

import hashlib

from openings.documents import DocumentCreate, UploadReservation

PDF = b"%PDF-1.4\nSynthetic test PDF"
# A CV source with macros, accents and comments, and the text derived from it.
SOURCE = r"""\documentclass{article}
\usepackage{hyperref}
\newcommand{\role}[2]{\textbf{#1} \hfill #2}
\newcommand{\myname}{Alex Example}
\begin{document}
{\LARGE \myname}\\[3pt]
\href{https://example.test}{example.test}
\section*{Experience}
\role{Backend Engineer --- Example Cloud}{2021--present}
\begin{itemize}[leftmargin=*]
  \item Reduced API p95 latency by 20\% through tracing. % measured on staging
  \item Built \textcolor{blue}{Python} services for Caf\'e~Example in M\"{u}nchen.
\end{itemize}
\vspace{4pt}{\small Skills: Python, SQL.}

Thank you for
your time.
\end{document}
"""
TEXT = """Alex Example
example.test

Experience
Backend Engineer — Example Cloud 2021–present
• Reduced API p95 latency by 20% through tracing.
• Built Python services for Café Example in München.
Skills: Python, SQL.

Thank you for your time."""


def tex(text="Synthetic content."):
    """A small synthetic LaTeX source whose derived text is ``text``."""
    return (
        "\\documentclass{article}\n\\begin{document}\n"
        + text.replace("%", "\\%")
        + "\n\\end{document}\n"
    ).encode()


def upload(documents, put, document_id, name, data, media_type, source_sha256=None):
    """Reserve and send one file of a revision; ``put`` is a test client's put."""
    grant = documents.reserve_upload(
        UploadReservation(
            owner_type="document",
            owner_id=document_id,
            name=name,
            size=len(data),
            media_type=media_type,
            source_sha256=source_sha256,
        )
    )
    return put(grant["url"], headers=grant["headers"], content=data)


def attach_pdf(documents, put, document_id, text="Synthetic content.", name="document"):
    """Upload the PDF built from the source ``tex(text)`` the revision already has."""
    response = upload(
        documents,
        put,
        document_id,
        f"{name}.pdf",
        PDF,
        "application/pdf",
        hashlib.sha256(tex(text)).hexdigest(),
    )
    assert response.status_code == 200, response.text
    return documents.get_document(document_id)


def attach(documents, put, document_id, text="Synthetic content.", pdf=True, name="document"):
    """Upload a revision's source and, when ``pdf``, the PDF built from it."""
    response = upload(documents, put, document_id, f"{name}.tex", tex(text), "application/x-tex")
    assert response.status_code == 200, response.text
    if pdf:
        return attach_pdf(documents, put, document_id, text, name)
    return documents.get_document(document_id)


def source_revision(
    documents, put, application_id, kind="cv", text="Synthetic content.", **options
):
    """A CV or letter revision with its source and its PDF (unless pdf=False)."""
    pdf = options.pop("pdf", True)
    document = documents.create_document(
        DocumentCreate(
            application_id=application_id, kind=kind, **options, pdf={"name": "cv.pdf", "size": 1}
        )
    )
    return attach(documents, put, document["id"], text, pdf)


def pdf_revision(documents, put, application_id, kind="cv", data=PDF, **options):
    """A complete PDF-only CV or letter revision, uploaded with the grant its create returns."""
    document = documents.create_document(
        DocumentCreate(
            application_id=application_id,
            kind=kind,
            pdf={"name": f"{kind}.pdf", "size": len(data)},
            **options,
        )
    )
    grant = document["uploads"]["pdf"]
    response = put(grant["url"], headers=grant["headers"], content=data)
    assert response.status_code == 200, response.text
    return documents.get_document(document["id"])


def text_pdf(*lines):
    """A small valid PDF whose page shows ``lines`` in Helvetica, for text extraction."""
    content = (
        "BT /F1 12 Tf 72 720 Td 14 TL "
        + " ".join(
            "(" + line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") '"
            for line in lines
        )
        + " ET"
    )
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
    ]
    out, offsets = "%PDF-1.4\n", []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


def guided_application(workspace, job_id, text, **fields):
    """Start an application whose standing guidance is its pinned note."""
    application = workspace.create_application({"job_id": job_id, **fields})
    workspace.add_note(job_id, {"body": text, "application_id": application["id"], "pinned": True})
    return workspace.get_application(application["id"])
