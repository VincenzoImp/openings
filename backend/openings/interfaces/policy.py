"""REST routes and MCP tools of policy."""

from ..policy import (
    PolicyItemCreate,
    PolicyItemUpdate,
    PolicyMove,
    PolicyReorder,
    PolicyService,
    PolicyVersion,
    RulePreview,
    Section,
)


def register_api(router, policy: PolicyService):
    @router.get("/policy")
    def policy_get():
        return policy.get_policy()

    @router.get("/policy/{section}")
    def policy_get_section(section: Section):
        return policy.get_policy(section)

    @router.post("/policy/rules/preview")
    def policy_rule_preview(value: RulePreview):
        return policy.preview_rule(value)

    @router.post("/policy/{section}/items", status_code=201)
    def policy_add(section: Section, value: PolicyItemCreate):
        return policy.add_item(section, value)

    @router.post("/policy/{section}/reorder")
    def policy_reorder(section: Section, value: PolicyReorder):
        return policy.reorder_items(section, value)

    @router.patch("/policy/items/{item_id}")
    def policy_update(item_id: str, value: PolicyItemUpdate):
        return policy.update_item(item_id, value)

    @router.post("/policy/items/{item_id}/confirm")
    def policy_confirm(item_id: str, value: PolicyVersion):
        return policy.confirm_item(item_id, value)

    @router.post("/policy/items/{item_id}/move")
    def policy_move(item_id: str, value: PolicyMove):
        return policy.move_item(item_id, value)

    @router.delete("/policy/items/{item_id}")
    def policy_remove(item_id: str, expected_version: int):
        return policy.remove_item(item_id, expected_version)


def register_mcp(mcp, policy: PolicyService):
    from mcp.types import ToolAnnotations

    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    write = ToolAnnotations(destructiveHint=False, openWorldHint=False)
    remove = ToolAnnotations(destructiveHint=True, openWorldHint=False)

    @mcp.tool(annotations=read)
    def policy_get(section: Section | None = None) -> dict:
        """Read the owner's policy: the sections decision (rules for shortlisting and dismissing), eligibility (facts employers ask about), writing (document rules with scope cv, letter or all) and facts, each with its own version and items. Omit section for all four plus the signal registry. An item with confirmed=false is a proposal or a value copied from the old Profile: do not rely on it; ask the owner to confirm it."""
        return policy.get_policy(section)

    @mcp.tool(annotations=read)
    def policy_rule_preview(value: RulePreview) -> dict:
        """Dry run of a decision rule: how many jobs waiting in the Inbox it matches now (matches), how many have no signals yet (pending), out of inbox, with up to five examples. Nothing is dismissed: an enabled rule the owner confirmed acts only on new jobs. Use it before proposing a rule."""
        return policy.preview_rule(value)

    @mcp.tool(annotations=write)
    def policy_add(section: Section, value: PolicyItemCreate) -> dict:
        """Add a policy item with the section's current version: a short label, the statement in the owner's words, an optional typed value and note. An agent token's item is a proposal until the owner confirms it (policy_confirm is owner only). Use an idempotency key for retries."""
        return policy.add_item(section, value)

    @mcp.tool(annotations=write)
    def policy_update(item_id: str, value: PolicyItemUpdate) -> dict:
        """Edit a policy item with its section's current version; omitted fields stay, and value, scope or rule accept null to clear. A content change by an agent token makes the item a proposal again and switches its rule off; enabling a rule needs owner authority."""
        return policy.update_item(item_id, value)

    @mcp.tool(annotations=write)
    def policy_move(item_id: str, value: PolicyMove) -> dict:
        """Move a policy item to the end of another section, with the current versions of both sections; use it to sort items copied from the old Profile out of facts. Its confirmation stays."""
        return policy.move_item(item_id, value)

    @mcp.tool(annotations=write)
    def policy_reorder(section: Section, value: PolicyReorder) -> dict:
        """Put a section's items in a new order, with the section's current version: item_ids lists every item id of the section once."""
        return policy.reorder_items(section, value)

    @mcp.tool(annotations=write)
    def policy_confirm(item_id: str, value: PolicyVersion) -> dict:
        """Confirm a proposed policy item as it stands, with its section's current version. Owner only: an agent token is refused with forbidden and asks the owner instead."""
        return policy.confirm_item(item_id, value)

    @mcp.tool(annotations=remove)
    def policy_remove(item_id: str, expected_version: int) -> dict:
        """Permanently remove a policy item, with its section's current version. Contexts already prepared keep their frozen copy."""
        return policy.remove_item(item_id, expected_version)
