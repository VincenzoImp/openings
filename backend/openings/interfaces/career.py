"""REST routes and MCP tools of career."""

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


def register_api(router, career: CareerService):
    @router.get("/career/profile")
    def get_profile():
        return career.get_profile()

    @router.patch("/career/profile")
    def update_profile(value: ProfileUpdate):
        return career.update_profile(value)

    @router.get("/career/knowledge")
    def list_knowledge(
        q: str = "", kind: str = "", limit: int = 100, offset: int = 0, summary: bool = False
    ):
        return career.list_knowledge(q, kind, limit, offset, summary)

    @router.post("/career/knowledge", status_code=201)
    def create_knowledge(value: KnowledgeCreate):
        return career.create_knowledge(value)

    @router.get("/career/knowledge/{knowledge_id}")
    def get_knowledge(knowledge_id: str):
        return career.get_knowledge(knowledge_id)

    @router.patch("/career/knowledge/{knowledge_id}")
    def update_knowledge(knowledge_id: str, value: KnowledgeUpdate):
        return career.update_knowledge(knowledge_id, value)

    @router.delete("/career/knowledge/{knowledge_id}")
    def delete_knowledge(knowledge_id: str, expected_version: int):
        return career.delete_knowledge(knowledge_id, expected_version)

    @router.get("/career/claims")
    def list_claims(
        knowledge_id: str = "",
        approved: bool | None = None,
        limit: int = 100,
        offset: int = 0,
        summary: bool = False,
        q: str = "",
    ):
        return career.list_claims(knowledge_id, approved, limit, offset, summary, q)

    @router.post("/career/claims", status_code=201)
    def create_claim(value: ClaimCreate):
        return career.create_claim(value)

    @router.get("/career/claims/{claim_id}")
    def get_claim(claim_id: str):
        return career.get_claim(claim_id)

    @router.patch("/career/claims/{claim_id}")
    def update_claim(claim_id: str, value: ClaimUpdate):
        return career.update_claim(claim_id, value)

    @router.delete("/career/claims/{claim_id}")
    def delete_claim(claim_id: str, expected_version: int):
        return career.delete_claim(claim_id, expected_version)

    @router.get("/templates")
    def list_templates(
        kind: str = "", limit: int = 100, offset: int = 0, summary: bool = False, q: str = ""
    ):
        return career.list_templates(kind, limit, offset, summary, q)

    @router.post("/templates", status_code=201)
    def create_template(value: TemplateCreate):
        return career.create_template(value)

    @router.get("/templates/{template_id}")
    def get_template(template_id: str):
        return career.get_template(template_id)

    @router.patch("/templates/{template_id}")
    def update_template(template_id: str, value: TemplateUpdate):
        return career.update_template(template_id, value)

    @router.delete("/templates/{template_id}")
    def delete_template(template_id: str, expected_version: int):
        return career.delete_template(template_id, expected_version)

    @router.get("/instructions")
    def get_instructions():
        return career.get_instructions()

    @router.patch("/instructions")
    def update_instructions(value: InstructionsUpdate):
        return career.update_instructions(value)

    @router.post("/career/import/preview")
    def preview_import(value: ImportPreview):
        return career.preview_import(value)

    @router.post("/career/import", status_code=201)
    def import_knowledge(value: CareerImport):
        return career.import_knowledge(value)


def register_mcp(mcp, career: CareerService):
    from mcp.types import ToolAnnotations

    for name, handler in [
        ("career_get_profile", career.get_profile),
        ("career_update_profile", career.update_profile),
        ("knowledge_list", career.list_knowledge),
        ("knowledge_get", career.get_knowledge),
        ("knowledge_create", career.create_knowledge),
        ("knowledge_update", career.update_knowledge),
        ("knowledge_delete", career.delete_knowledge),
        ("claims_list", career.list_claims),
        ("claims_get", career.get_claim),
        ("claims_create", career.create_claim),
        ("claims_update", career.update_claim),
        ("claims_delete", career.delete_claim),
        ("templates_list", career.list_templates),
        ("templates_get", career.get_template),
        ("templates_create", career.create_template),
        ("templates_update", career.update_template),
        ("templates_delete", career.delete_template),
        ("instructions_get", career.get_instructions),
        ("instructions_update", career.update_instructions),
        ("career_preview_import", career.preview_import),
        ("career_import", career.import_knowledge),
    ]:
        read_only = name.endswith(("_get", "_list")) or name in {
            "career_get_profile",
            "career_preview_import",
            "instructions_get",
        }
        mcp.add_tool(
            handler,
            name=name,
            annotations=ToolAnnotations(
                readOnlyHint=read_only,
                destructiveHint=name.endswith("_delete"),
                idempotentHint=read_only
                or name
                in {
                    "career_update_profile",
                    "instructions_update",
                    "knowledge_update",
                    "claims_update",
                    "templates_update",
                },
                openWorldHint=False,
            ),
        )
