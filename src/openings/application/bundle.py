"""One application as a zip: the posting, the notes, every attachment."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from openings.application.models import JobDetail
from openings.models import NoteKind


def _posting_markdown(detail: JobDetail) -> str:
    job = detail.job
    lines = [
        f"# {job.title}",
        "",
        f"**{job.company}**" + (f" · {job.location}" if job.location else ""),
        "",
    ]
    facts = [
        ("Status", job.status.value),
        ("Score", str(job.relevance_score)),
        ("Source", job.source),
        ("URL", job.job_url or ""),
        ("Posted", job.date_posted.isoformat() if job.date_posted else ""),
        ("First seen", job.first_seen.isoformat()),
        ("Last seen", job.last_seen.isoformat()),
        ("Type", job.job_type or ""),
        ("Level", job.job_level or ""),
        ("Labels", ", ".join(detail.labels)),
    ]
    for name, value in facts:
        if value:
            lines.append(f"- {name}: {value}")
    if detail.postings:
        lines.append("")
        lines.append("## Postings")
        lines.append("")
        for posting in detail.postings:
            lines.append(
                f"- {posting.source}: {posting.url or posting.key} "
                f"(seen {posting.first_seen.isoformat()} to {posting.last_seen.isoformat()})"
            )
    lines.append("")
    lines.append("## Description")
    lines.append("")
    lines.append(job.description or "_No description stored._")
    return "\n".join(lines) + "\n"


def _notes_markdown(detail: JobDetail) -> str:
    lines = ["# Notes", ""]
    answers = [note for note in detail.notes if note.kind is NoteKind.QA]
    notes = [note for note in detail.notes if note.kind is NoteKind.NOTE]
    if answers:
        lines.append("## Form questions and answers")
        lines.append("")
        for note in answers:
            lines.append(f"### {note.title or 'Question'}")
            lines.append("")
            lines.append(note.body)
            lines.append("")
    if notes:
        lines.append("## Notes")
        lines.append("")
        for note in notes:
            stamp = note.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"### {note.title or stamp}")
            lines.append("")
            lines.append(note.body)
            lines.append("")
    if not answers and not notes:
        lines.append("_No notes._")
    return "\n".join(lines) + "\n"


def _timeline_markdown(detail: JobDetail) -> str:
    lines = ["# Timeline", ""]
    for event in detail.events:
        lines.append(f"- {event.created_at.isoformat()} · {event.kind.value}: {event.summary}")
    return "\n".join(lines) + "\n"


def build_bundle(detail: JobDetail, files: list[tuple[str, Path]]) -> bytes:
    """A zip with ``posting.md``, ``notes.md``, ``timeline.md``, ``job.json`` and the files."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("posting.md", _posting_markdown(detail))
        archive.writestr("notes.md", _notes_markdown(detail))
        archive.writestr("timeline.md", _timeline_markdown(detail))
        archive.writestr("job.json", json.dumps(detail.to_dict(), ensure_ascii=False, indent=2))
        used: set[str] = set()
        for filename, path in files:
            name = filename
            stem, suffix = Path(filename).stem, Path(filename).suffix
            counter = 2
            while name in used:
                name = f"{stem} ({counter}){suffix}"
                counter += 1
            used.add(name)
            if path.is_file():
                archive.write(path, f"attachments/{name}")
    return buffer.getvalue()
