"""REST routes and MCP tools of career."""

from mcp.types import ToolAnnotations

from ..career import (
    CareerImport,
    CareerService,
    ClaimCreate,
    ClaimUpdate,
    ImportPreview,
    InstructionsUpdate,
    KnowledgeCreate,
    KnowledgeUpdate,
    ProfileUpdate,
    TemplateCreate,
    TemplateUpdate,
)
from ..career.models import ClaimQuery, KnowledgeQuery, TemplateQuery
from .registry import Operation, Param, Route, Tool, bind_mcp, bind_rest, query_model

LOOKUP = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
REPLACE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
ADD = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)
DELETE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False
)

OPERATIONS = (
    Operation(
        "profile.read",
        "profile",
        "get",
        "Career and templates",
        "Read profile, links, metadata and version",
        params=(),
        call=lambda s: s.get_profile(),
        rest=(Route("GET", "/career/profile", "get_profile"),),
        aliases=("career_get_profile",),
        tool=Tool(LOOKUP, method="get_profile"),
    ),
    Operation(
        "profile.update",
        "profile",
        "update",
        "Career and templates",
        "Edit profile/preferences/contact",
        params=(Param("value", ProfileUpdate),),
        call=lambda s, value: s.update_profile(value),
        rest=(Route("PATCH", "/career/profile", "update_profile"),),
        aliases=("career_update_profile",),
        tool=Tool(REPLACE, method="update_profile"),
    ),
    Operation(
        "knowledge.list",
        "knowledge",
        "list",
        "Career and templates",
        "Search/filter paginated career entries summaries",
        params=(query_model(KnowledgeQuery),),
        call=lambda s, value: s.list_knowledge(**(value or KnowledgeQuery()).model_dump()),
        rest=(Route("GET", "/career/knowledge", "list_knowledge"),),
        tool=Tool(
            LOOKUP,
            CareerService.list_knowledge.__doc__,
            legacy=tuple(KnowledgeQuery.model_fields),
        ),
    ),
    Operation(
        "knowledge.create",
        "knowledge",
        "create",
        "Career and templates",
        "Create career entries",
        params=(Param("value", KnowledgeCreate),),
        call=lambda s, value: s.create_knowledge(value),
        rest=(Route("POST", "/career/knowledge", "create_knowledge", status_code=201),),
        tool=Tool(ADD, method="create_knowledge"),
    ),
    Operation(
        "knowledge.read",
        "knowledge",
        "get",
        "Career and templates",
        "Read full career entries",
        params=(Param("knowledge_id", str),),
        call=lambda s, knowledge_id: s.get_knowledge(knowledge_id),
        rest=(Route("GET", "/career/knowledge/{knowledge_id}", "get_knowledge"),),
        tool=Tool(LOOKUP, method="get_knowledge"),
    ),
    Operation(
        "knowledge.update",
        "knowledge",
        "update",
        "Career and templates",
        "Edit career entries with version protection",
        params=(Param("knowledge_id", str), Param("value", KnowledgeUpdate)),
        call=lambda s, knowledge_id, value: s.update_knowledge(knowledge_id, value),
        rest=(Route("PATCH", "/career/knowledge/{knowledge_id}", "update_knowledge"),),
        tool=Tool(REPLACE, method="update_knowledge"),
    ),
    Operation(
        "knowledge.delete",
        "knowledge",
        "delete",
        "Career and templates",
        "Delete live career entries",
        params=(Param("knowledge_id", str), Param("expected_version", int)),
        call=lambda s, knowledge_id, expected_version: s.delete_knowledge(
            knowledge_id, expected_version
        ),
        rest=(Route("DELETE", "/career/knowledge/{knowledge_id}", "delete_knowledge"),),
        tool=Tool(DELETE, method="delete_knowledge"),
    ),
    Operation(
        "claims.list",
        "claims",
        "list",
        "Career and templates",
        "Search/filter paginated claims summaries",
        params=(query_model(ClaimQuery),),
        call=lambda s, value: s.list_claims(**(value or ClaimQuery()).model_dump()),
        rest=(Route("GET", "/career/claims", "list_claims"),),
        tool=Tool(LOOKUP, CareerService.list_claims.__doc__, legacy=tuple(ClaimQuery.model_fields)),
    ),
    Operation(
        "claims.create",
        "claims",
        "create",
        "Career and templates",
        "Create claim",
        params=(Param("value", ClaimCreate),),
        call=lambda s, value: s.create_claim(value),
        rest=(Route("POST", "/career/claims", "create_claim", status_code=201),),
        tool=Tool(ADD, method="create_claim"),
    ),
    Operation(
        "claims.read",
        "claims",
        "get",
        "Career and templates",
        "Read full claim",
        params=(Param("claim_id", str),),
        call=lambda s, claim_id: s.get_claim(claim_id),
        rest=(Route("GET", "/career/claims/{claim_id}", "get_claim"),),
        tool=Tool(LOOKUP, method="get_claim"),
    ),
    Operation(
        "claims.update",
        "claims",
        "update",
        "Career and templates",
        "Edit claim with version protection",
        params=(Param("claim_id", str), Param("value", ClaimUpdate)),
        call=lambda s, claim_id, value: s.update_claim(claim_id, value),
        rest=(Route("PATCH", "/career/claims/{claim_id}", "update_claim"),),
        tool=Tool(REPLACE, method="update_claim"),
    ),
    Operation(
        "claims.delete",
        "claims",
        "delete",
        "Career and templates",
        "Delete live claim",
        params=(Param("claim_id", str), Param("expected_version", int)),
        call=lambda s, claim_id, expected_version: s.delete_claim(claim_id, expected_version),
        rest=(Route("DELETE", "/career/claims/{claim_id}", "delete_claim"),),
        tool=Tool(DELETE, method="delete_claim"),
    ),
    Operation(
        "templates.list",
        "templates",
        "list",
        "Career and templates",
        "Search/filter paginated templates summaries",
        params=(query_model(TemplateQuery),),
        call=lambda s, value: s.list_templates(**(value or TemplateQuery()).model_dump()),
        rest=(Route("GET", "/templates", "list_templates"),),
        tool=Tool(
            LOOKUP,
            CareerService.list_templates.__doc__,
            legacy=tuple(TemplateQuery.model_fields),
        ),
    ),
    Operation(
        "templates.create",
        "templates",
        "create",
        "Career and templates",
        "Create template",
        params=(Param("value", TemplateCreate),),
        call=lambda s, value: s.create_template(value),
        rest=(Route("POST", "/templates", "create_template", status_code=201),),
        tool=Tool(ADD, method="create_template"),
    ),
    Operation(
        "templates.read",
        "templates",
        "get",
        "Career and templates",
        "Read full template",
        params=(Param("template_id", str),),
        call=lambda s, template_id: s.get_template(template_id),
        rest=(Route("GET", "/templates/{template_id}", "get_template"),),
        tool=Tool(LOOKUP, method="get_template"),
    ),
    Operation(
        "templates.update",
        "templates",
        "update",
        "Career and templates",
        "Edit template with version protection",
        params=(Param("template_id", str), Param("value", TemplateUpdate)),
        call=lambda s, template_id, value: s.update_template(template_id, value),
        rest=(Route("PATCH", "/templates/{template_id}", "update_template"),),
        tool=Tool(REPLACE, method="update_template"),
    ),
    Operation(
        "templates.delete",
        "templates",
        "delete",
        "Career and templates",
        "Delete live template",
        params=(Param("template_id", str), Param("expected_version", int)),
        call=lambda s, template_id, expected_version: s.delete_template(
            template_id, expected_version
        ),
        rest=(Route("DELETE", "/templates/{template_id}", "delete_template"),),
        tool=Tool(DELETE, method="delete_template"),
    ),
    Operation(
        "instructions.read",
        "instructions",
        "get",
        "Career and templates",
        "Read general document writing instructions",
        params=(),
        call=lambda s: s.get_instructions(),
        rest=(Route("GET", "/instructions", "get_instructions"),),
        tool=Tool(LOOKUP, method="get_instructions"),
    ),
    Operation(
        "instructions.update",
        "instructions",
        "update",
        "Career and templates",
        "Edit general document writing instructions",
        params=(Param("value", InstructionsUpdate),),
        call=lambda s, value: s.update_instructions(value),
        rest=(Route("PATCH", "/instructions", "update_instructions"),),
        tool=Tool(REPLACE, method="update_instructions"),
    ),
    Operation(
        "career.preview_import",
        "career",
        "preview_import",
        "Career and templates",
        "Preview JSON/text career import without mutation",
        params=(Param("value", ImportPreview),),
        call=lambda s, value: s.preview_import(value),
        rest=(Route("POST", "/career/import/preview", "preview_import"),),
        tool=Tool(LOOKUP, method="preview_import"),
    ),
    Operation(
        "career.import",
        "career",
        "import",
        "Career and templates",
        "Confirm append-only evidence and optional versioned profile import",
        params=(Param("value", CareerImport),),
        call=lambda s, value: s.import_knowledge(value),
        rest=(Route("POST", "/career/import", "import_knowledge", status_code=201),),
        tool=Tool(ADD, method="import_knowledge"),
    ),
)


def register_api(router, career: CareerService):
    bind_rest(router, OPERATIONS, career)


def register_mcp(mcp, career: CareerService):
    bind_mcp(mcp, OPERATIONS, career)
