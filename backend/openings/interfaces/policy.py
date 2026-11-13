"""REST routes and MCP tools of policy."""

from mcp.types import ToolAnnotations

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
from .registry import REQUIRED, Operation, Param, Route, Tool, bind_mcp, bind_rest

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
WRITE = ToolAnnotations(destructiveHint=False, openWorldHint=False)
REMOVE = ToolAnnotations(destructiveHint=True, openWorldHint=False)

OPERATIONS = (
    Operation(
        "policy.read",
        "policy",
        "get",
        "Career and templates",
        "Read the owner's policy, or one section",
        params=(Param("section", Section | None, None, rest=(Section, REQUIRED)),),
        call=lambda s, section: s.get_policy(section),
        rest=(
            Route("GET", "/policy", "policy_get", params=(), call=lambda s: s.get_policy()),
            Route("GET", "/policy/{section}", "policy_get_section"),
        ),
        tool=Tool(
            READ,
            "Read the owner's policy: the sections decision (rules for shortlisting and dismissing), eligibility (facts employers ask about), writing (document rules with scope cv, letter or all) and facts, each with its own version and items. Omit section for all four plus the signal registry. An item with confirmed=false is a proposal or a value copied from the old Profile: do not rely on it; ask the owner to confirm it.",
        ),
    ),
    Operation(
        "policy.rule_preview",
        "policy",
        "rule_preview",
        "Career and templates",
        "Count the jobs to review a decision rule matches now, without acting",
        params=(Param("value", RulePreview),),
        call=lambda s, value: s.preview_rule(value),
        rest=(Route("POST", "/policy/rules/preview", "policy_rule_preview"),),
        tool=Tool(
            READ,
            "Dry run of a decision rule: how many jobs waiting in the Inbox it matches now (matches), how many have no signals yet (pending), out of inbox, with up to five examples. Nothing is dismissed: an enabled rule the owner confirmed acts only on new jobs. Use it before proposing a rule.",
        ),
    ),
    Operation(
        "policy.add",
        "policy",
        "add",
        "Career and templates",
        "Add a policy item",
        params=(Param("section", Section), Param("value", PolicyItemCreate)),
        call=lambda s, section, value: s.add_item(section, value),
        rest=(Route("POST", "/policy/{section}/items", "policy_add", status_code=201),),
        tool=Tool(
            WRITE,
            "Add a policy item with the section's current version: a short label, the statement in the owner's words, an optional typed value and note. An agent token's item is a proposal until the owner confirms it (policy_confirm is owner only). Use an idempotency key for retries.",
        ),
    ),
    Operation(
        "policy.reorder",
        "policy",
        "reorder",
        "Career and templates",
        "Reorder a section's policy items",
        params=(Param("section", Section), Param("value", PolicyReorder)),
        call=lambda s, section, value: s.reorder_items(section, value),
        rest=(Route("POST", "/policy/{section}/reorder", "policy_reorder"),),
        tool=Tool(
            WRITE,
            "Put a section's items in a new order, with the section's current version: item_ids lists every item id of the section once.",
        ),
    ),
    Operation(
        "policy.update",
        "policy",
        "update",
        "Career and templates",
        "Edit a policy item",
        params=(Param("item_id", str), Param("value", PolicyItemUpdate)),
        call=lambda s, item_id, value: s.update_item(item_id, value),
        rest=(Route("PATCH", "/policy/items/{item_id}", "policy_update"),),
        tool=Tool(
            WRITE,
            "Edit a policy item with its section's current version; omitted fields stay, and value, scope or rule accept null to clear. A content change by an agent token makes the item a proposal again and switches its rule off; enabling a rule needs owner authority.",
        ),
    ),
    Operation(
        "policy.confirm",
        "policy",
        "confirm",
        "Career and templates",
        "Confirm a proposed policy item",
        access="owner",
        params=(Param("item_id", str), Param("value", PolicyVersion)),
        call=lambda s, item_id, value: s.confirm_item(item_id, value),
        rest=(Route("POST", "/policy/items/{item_id}/confirm", "policy_confirm"),),
        tool=Tool(
            WRITE,
            "Confirm a proposed policy item as it stands, with its section's current version. Owner only: an agent token is refused with forbidden and asks the owner instead.",
        ),
    ),
    Operation(
        "policy.move",
        "policy",
        "move",
        "Career and templates",
        "Move a policy item to another section",
        params=(Param("item_id", str), Param("value", PolicyMove)),
        call=lambda s, item_id, value: s.move_item(item_id, value),
        rest=(Route("POST", "/policy/items/{item_id}/move", "policy_move"),),
        tool=Tool(
            WRITE,
            "Move a policy item to the end of another section, with the current versions of both sections; use it to sort items copied from the old Profile out of facts. Its confirmation stays.",
        ),
    ),
    Operation(
        "policy.remove",
        "policy",
        "remove",
        "Career and templates",
        "Remove a policy item",
        params=(Param("item_id", str), Param("expected_version", int)),
        call=lambda s, item_id, expected_version: s.remove_item(item_id, expected_version),
        rest=(Route("DELETE", "/policy/items/{item_id}", "policy_remove"),),
        tool=Tool(
            REMOVE,
            "Permanently remove a policy item, with its section's current version. Contexts already prepared keep their frozen copy.",
        ),
    ),
)


def register_api(router, policy: PolicyService):
    bind_rest(router, OPERATIONS, policy)


def register_mcp(mcp, policy: PolicyService):
    bind_mcp(mcp, OPERATIONS, policy)
