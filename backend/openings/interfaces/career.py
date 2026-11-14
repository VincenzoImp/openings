"""Operations of the Profile, career entries, highlights, templates and the career import.

An agent reads the profile, a career summary and the templates in workspace_context,
whole entries with career_get, and writes in batches (career_save, highlights_save).
The one-record routes stay on REST for the dashboard and scripts; the career import
is the owner's (an agent reads a CV itself and saves what it finds).
"""

from ..career import (
    CareerImport,
    EntryCreate,
    EntryUpdate,
    HighlightCreate,
    HighlightUpdate,
    ImportPreview,
    ProfileUpdate,
    TemplateCreate,
    TemplateUpdate,
)
from ..career.models import (
    CareerRead,
    CareerSave,
    EntryQuery,
    HighlightQuery,
    HighlightsSave,
    TemplateQuery,
    TemplateSave,
)
from ..responses import (
    BatchResult,
    CareerBatch,
    CareerEntry,
    CareerPage,
    Deleted,
    Highlight,
    HighlightPage,
    ImportPreviewResult,
    ImportResult,
    Profile,
    Template,
    TemplatePage,
)
from .core import Version
from .operation import DESTRUCTIVE, OWNER, WRITE, WS, Q, operation


@operation("GET /career/profile", tags=["career"], mcp="workspace_context")
def profile_get(ws: WS) -> Profile:
    """Read the profile and its version."""
    return ws.career.get_profile()


@operation("PATCH /career/profile", access=WRITE, tags=["career"])
def profile_update(ws: WS, body: ProfileUpdate) -> Profile:
    """Edit the profile, with its version.

    Name, contact, headline, location, summary, links and metadata; omitted fields stay.
    """
    return ws.career.update_profile(body)


@operation("GET /career/batch", tags=["career"])
def career_get(ws: WS, query: Q[CareerRead]) -> CareerBatch:
    """Read up to 50 career entries in full, with highlights and files.

    By ids, or the entries matching q and kind.
    """
    return ws.career.read_career(query)


@operation("POST /career/batch", access=WRITE, tags=["career"])
def career_save(ws: WS, body: CareerSave) -> BatchResult:
    """Add or update up to 50 career entries.

    An item with career_id and expected_version updates; without, adds. Facts come from the
    owner, never from a job posting.
    """
    return ws.career.save_career(body)


@operation("GET /career/entries", tags=["career"], mcp="career_get")
def career_list(ws: WS, query: Q[EntryQuery]) -> CareerPage:
    """Search career entries by q and kind; summary=false returns full records."""
    return ws.career.list_entries(**query.model_dump())


@operation("POST /career/entries", access=WRITE, status=201, tags=["career"], mcp="career_save")
def career_create(ws: WS, body: EntryCreate) -> CareerEntry:
    """Add a career entry."""
    return ws.career.create_entry(body)


@operation("PATCH /career/entries/{career_id}", access=WRITE, tags=["career"], mcp="career_save")
def career_update(ws: WS, career_id: str, body: EntryUpdate) -> CareerEntry:
    """Edit a career entry, with its version; dates=null clears the dates."""
    return ws.career.update_entry(career_id, body)


@operation("DELETE /career/entries/{career_id}", access=DESTRUCTIVE, tags=["career"])
def career_delete(ws: WS, career_id: str, expected_version: Version) -> Deleted:
    """Delete a career entry permanently, with its highlights and files.

    Only on the owner's explicit request; document revisions are unchanged.
    """
    return ws.career.delete_entry(career_id, expected_version)


@operation("POST /career/highlights/batch", access=WRITE, tags=["highlights"])
def highlights_save(ws: WS, body: HighlightsSave) -> BatchResult:
    """Add, update or approve up to 100 highlights.

    Reusable wording on a career entry (career_id). highlight_id with expected_version
    updates. always_include: use it in every CV unless the job argues against it.
    """
    return ws.career.save_highlights(body)


@operation("GET /career/highlights", tags=["highlights"], mcp="career_get")
def highlights_list(ws: WS, query: Q[HighlightQuery]) -> HighlightPage:
    """Search highlights by entry (career_id), approval or text (q)."""
    return ws.career.list_highlights(**query.model_dump())


@operation(
    "POST /career/highlights", access=WRITE, status=201, tags=["highlights"], mcp="highlights_save"
)
def highlights_create(ws: WS, body: HighlightCreate) -> Highlight:
    """Add a highlight; not approved by default."""
    return ws.career.create_highlight(body)


@operation(
    "PATCH /career/highlights/{highlight_id}",
    access=WRITE,
    tags=["highlights"],
    mcp="highlights_save",
)
def highlights_update(ws: WS, highlight_id: str, body: HighlightUpdate) -> Highlight:
    """Edit or approve a highlight, with its version."""
    return ws.career.update_highlight(highlight_id, body)


@operation("DELETE /career/highlights/{highlight_id}", access=DESTRUCTIVE, tags=["highlights"])
def highlights_delete(ws: WS, highlight_id: str, expected_version: Version) -> Deleted:
    """Delete a highlight permanently.

    With its version; document revisions keep the ids they cite.
    """
    return ws.career.delete_highlight(highlight_id, expected_version)


@operation("GET /templates", tags=["templates"], mcp="workspace_context")
def templates_list(ws: WS, query: Q[TemplateQuery]) -> TemplatePage:
    """List templates by kind or q; summary=false adds TeX, guidance and rules."""
    return ws.career.list_templates(**query.model_dump())


@operation("POST /templates/save", access=WRITE, tags=["templates"])
def templates_save(ws: WS, body: TemplateSave) -> Template:
    """Add a template, or update one (template_id, expected_version).

    TeX source, guidance, limits (rules) and is_default; the first of a kind is the default.
    """
    return ws.career.save_template(body)


@operation("POST /templates", access=WRITE, status=201, tags=["templates"], mcp="templates_save")
def templates_create(ws: WS, body: TemplateCreate) -> Template:
    """Add a template."""
    return ws.career.create_template(body)


@operation("GET /templates/{template_id}", tags=["templates"])
def templates_get(ws: WS, template_id: str) -> Template:
    """Read a template: TeX source, guidance, limits and its files.

    Compile CV and letter from it on your machine.
    """
    template = ws.career.get_template(template_id)
    files = ws.documents.list_files(owner_type="template", owner_id=template_id, limit=200)
    return template | {"files": files["items"]}


@operation("PATCH /templates/{template_id}", access=WRITE, tags=["templates"], mcp="templates_save")
def templates_update(ws: WS, template_id: str, body: TemplateUpdate) -> Template:
    """Edit a template, with its version."""
    return ws.career.update_template(template_id, body)


@operation("DELETE /templates/{template_id}", access=DESTRUCTIVE, tags=["templates"])
def templates_delete(ws: WS, template_id: str, expected_version: Version) -> Deleted:
    """Delete a template permanently, with its files.

    Only on the owner's explicit request; document revisions are unchanged.
    """
    return ws.career.delete_template(template_id, expected_version)


@operation("POST /career/import/preview", access=OWNER, tags=["owner"])
def career_preview_import(ws: WS, body: ImportPreview) -> ImportPreviewResult:
    """Preview a career import (owner only).

    Parses JSON or plain text into entries and profile fields without storing anything.
    """
    return ws.career.preview_import(body)


@operation("POST /career/import", access=OWNER, status=201, tags=["owner"])
def career_import(ws: WS, body: CareerImport) -> ImportResult:
    """Import previewed career entries (owner only).

    Appends the entries and, with the profile's version, applies the profile fields.
    """
    return ws.career.import_entries(body)
