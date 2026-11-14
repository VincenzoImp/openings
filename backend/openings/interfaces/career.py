"""Operations of the career record: profile, entries, highlights, templates and import."""

from ..career import (
    CareerImport,
    ClaimCreate,
    ClaimUpdate,
    ImportPreview,
    KnowledgeCreate,
    KnowledgeUpdate,
    ProfileUpdate,
    TemplateCreate,
    TemplateUpdate,
)
from ..career.models import ClaimQuery, KnowledgeQuery, TemplateQuery
from ..responses import (
    Claim,
    ClaimPage,
    Deleted,
    ImportPreviewResult,
    ImportResult,
    Knowledge,
    KnowledgePage,
    Profile,
    Template,
    TemplatePage,
)
from .core import Version
from .operation import DESTRUCTIVE, WRITE, WS, Q, operation


@operation("GET /career/profile", tags=["career"])
def profile_get(ws: WS) -> Profile:
    """Read the profile and its version."""
    return ws.career.get_profile()


@operation("PATCH /career/profile", access=WRITE, tags=["career"])
def profile_update(ws: WS, body: ProfileUpdate) -> Profile:
    """Edit the profile.

    Name, contact, headline, summary, links and metadata, with the profile's version.
    """
    return ws.career.update_profile(body)


@operation("GET /career/knowledge", tags=["career"])
def knowledge_list(ws: WS, query: Q[KnowledgeQuery]) -> KnowledgePage:
    """Search career entries.

    By q (title, organization, narrative) and kind. summary=true (default) returns previews
    and counts, summary=false full records; knowledge_get reads one.
    """
    return ws.career.list_knowledge(**query.model_dump())


@operation("POST /career/knowledge", access=WRITE, status=201, tags=["career"])
def knowledge_create(ws: WS, body: KnowledgeCreate) -> Knowledge:
    """Add a career entry.

    Facts come from the owner, never from a job posting.
    """
    return ws.career.create_knowledge(body)


@operation("GET /career/knowledge/{knowledge_id}", tags=["career"])
def knowledge_get(ws: WS, knowledge_id: str) -> Knowledge:
    """Read a career entry with its full narrative and metadata."""
    return ws.career.get_knowledge(knowledge_id)


@operation("PATCH /career/knowledge/{knowledge_id}", access=WRITE, tags=["career"])
def knowledge_update(ws: WS, knowledge_id: str, body: KnowledgeUpdate) -> Knowledge:
    """Edit a career entry.

    With its version; dates=null clears the dates. Document revisions keep the ids they cite.
    """
    return ws.career.update_knowledge(knowledge_id, body)


@operation("DELETE /career/knowledge/{knowledge_id}", access=DESTRUCTIVE, tags=["career"])
def knowledge_delete(ws: WS, knowledge_id: str, expected_version: Version) -> Deleted:
    """Delete a career entry.

    Permanently, with its highlights and files; document revisions are unchanged.
    """
    return ws.career.delete_knowledge(knowledge_id, expected_version)


@operation("GET /career/claims", tags=["highlights"])
def claims_list(ws: WS, query: Q[ClaimQuery]) -> ClaimPage:
    """Search highlights.

    By entry (knowledge_id), approval or text (q). summary=true (default) bounds previews and
    omits metadata; always_include is always returned.
    """
    return ws.career.list_claims(**query.model_dump())


@operation("POST /career/claims", access=WRITE, status=201, tags=["highlights"])
def claims_create(ws: WS, body: ClaimCreate) -> Claim:
    """Add a highlight.

    Reusable wording tied to a career entry; not approved by default. always_include puts it
    in every CV unless the job gives a reason to leave it out.
    """
    return ws.career.create_claim(body)


@operation("GET /career/claims/{claim_id}", tags=["highlights"])
def claims_get(ws: WS, claim_id: str) -> Claim:
    """Read a highlight and its entry id."""
    return ws.career.get_claim(claim_id)


@operation("PATCH /career/claims/{claim_id}", access=WRITE, tags=["highlights"])
def claims_update(ws: WS, claim_id: str, body: ClaimUpdate) -> Claim:
    """Edit or approve a highlight.

    With its version. Writing documents never approves new facts.
    """
    return ws.career.update_claim(claim_id, body)


@operation("DELETE /career/claims/{claim_id}", access=DESTRUCTIVE, tags=["highlights"])
def claims_delete(ws: WS, claim_id: str, expected_version: Version) -> Deleted:
    """Delete a highlight.

    Permanently; document revisions keep the ids they cite.
    """
    return ws.career.delete_claim(claim_id, expected_version)


@operation("GET /templates", tags=["templates"])
def templates_list(ws: WS, query: Q[TemplateQuery]) -> TemplatePage:
    """List templates.

    By kind or q. summary=true (default) omits TeX, guidance and rules. Read the template
    before editing or compiling externally.
    """
    return ws.career.list_templates(**query.model_dump())


@operation("POST /templates", access=WRITE, status=201, tags=["templates"])
def templates_create(ws: WS, body: TemplateCreate) -> Template:
    """Add a template.

    Source, guidance and rules; the first template of a kind becomes its default.
    """
    return ws.career.create_template(body)


@operation("GET /templates/{template_id}", tags=["templates"])
def templates_get(ws: WS, template_id: str) -> Template:
    """Read a template.

    Its source, guidance and rules (limits and settings); fetch its files separately.
    """
    return ws.career.get_template(template_id)


@operation("PATCH /templates/{template_id}", access=WRITE, tags=["templates"])
def templates_update(ws: WS, template_id: str, body: TemplateUpdate) -> Template:
    """Edit a template.

    Source, default, guidance or rules, with its version.
    """
    return ws.career.update_template(template_id, body)


@operation("DELETE /templates/{template_id}", access=DESTRUCTIVE, tags=["templates"])
def templates_delete(ws: WS, template_id: str, expected_version: Version) -> Deleted:
    """Delete a template.

    With its files; document revisions are unchanged.
    """
    return ws.career.delete_template(template_id, expected_version)


@operation("POST /career/import/preview", tags=["career"])
def career_preview_import(ws: WS, body: ImportPreview) -> ImportPreviewResult:
    """Preview a career import.

    Parses JSON or plain text into entries and profile fields without storing anything.
    """
    return ws.career.preview_import(body)


@operation("POST /career/import", access=WRITE, status=201, tags=["career"])
def career_import(ws: WS, body: CareerImport) -> ImportResult:
    """Import previewed career entries.

    Appends the entries and, with the profile's version, applies the profile fields.
    """
    return ws.career.import_knowledge(body)
