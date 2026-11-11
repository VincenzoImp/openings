"""The owner's policy: sections with their own version, owner confirmation, frozen copies and the upgrade."""

import hashlib
import json
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from context_fixtures import legacy_prepare_context, make_schema_eight
from openings.actors import OWNER, acting_as, token_actor
from openings.app import create_app
from openings.career import (
    CareerService,
    ClaimCreate,
    ClaimUpdate,
    KnowledgeCreate,
    ProfileUpdate,
    TemplateCreate,
    TemplateUpdate,
)
from openings.db import MIGRATIONS, SCHEMA_VERSION, Database
from openings.documents import ContextCreate, DocumentService
from openings.errors import DomainError
from openings.operations import restore_database
from openings.policy import SECTIONS, PolicyItemCreate, PolicyItemUpdate, PolicyService
from openings.snapshots import payload_text
from openings.workspace import Workspace
from policy_fixtures import SCHEMA_TEN_COLUMNS, make_schema_nine
from schema_fixtures import columns, index_names, table_names
from test_context_parts import seed

MCP_HEADERS = {"Accept": "application/json, text/event-stream"}
AGENT = token_actor("token-agent", "Synthetic agent", "agent")
OWNER_TOKEN = token_actor("token-owner", "Synthetic owner token", "owner")
METADATA = {
    "decision_policy": {"include": ["backend"], "exclude": ["sales"], "stretch": {"max": 2}},
    "work_authorization": "EU citizen — “synthetic” ✓",
    "notice_period_days": 30,
    "open_to_relocation": False,
    "salary": 95000.5,
    "languages": ["English", "Italian"],
    "unset": None,
    "Interview-availability": {"days": ["Tue", "Thu"], "from": "16:00"},
}
RULE = {
    "signal": "language_required",
    "condition": {"operator": "not_in", "value": ["English", "Italian"]},
    "action": "dismiss",
}


@pytest.fixture
def services(tmp_path):
    workspace = Workspace(tmp_path / "policy.sqlite")
    return workspace, PolicyService(workspace)


def refused(call, code, status=409):
    with pytest.raises(DomainError) as error:
        call()
    assert (error.value.status, error.value.code) == (status, code)
    return error.value


def versions(policy):
    return {section["section"]: section["version"] for section in policy.get_policy()["sections"]}


def test_sections_have_their_own_version_and_items_keep_a_dense_order(services):
    _, policy = services
    empty = policy.get_policy()
    assert [section["section"] for section in empty["sections"]] == list(SECTIONS)
    assert all(section["version"] == 0 and not section["items"] for section in empty["sections"])
    assert empty["signals_applied"] is False
    assert {signal["signal"] for signal in empty["signals"]} == {
        "language_required",
        "posting_language",
        "likely_duplicate",
        "no_longer_listed",
    }
    with acting_as(OWNER):
        first = policy.add_item(
            "writing",
            {"expected_version": 0, "label": " Weaknesses ", "statement": "Never volunteer them."},
        )
        assert first["section"]["version"] == 1
        item = first["item"]
        assert (item["label"], item["scope"], item["position"]) == ("Weaknesses", "all", 0)
        assert item["confirmed"] and item["confirmed_by"]["kind"] == "owner"
        assert (item["value"], item["value_type"], item["rule"], item["origin"]) == (
            None,
            None,
            None,
            None,
        )
        stale = refused(
            lambda: policy.add_item("writing", {"expected_version": 0, "label": "One page"}),
            "conflict",
        )
        assert stale.details == {"current_version": 1, "section": "writing"}
        second = policy.add_item(
            "writing",
            {
                "expected_version": 1,
                "label": "Letter length",
                "statement": "Three paragraphs.",
                "value": 200,
                "scope": "letter",
                "idempotency_key": "letter-length",
            },
        )
        # A retry with the same key returns the item, even with the version it had before.
        again = policy.add_item(
            "writing",
            {"expected_version": 1, "label": "Letter length", "idempotency_key": "letter-length"},
        )
        assert again["item"]["id"] == second["item"]["id"] and again["section"]["version"] == 2
        refused(
            lambda: policy.add_item(
                "facts",
                {"expected_version": 0, "label": "Other", "idempotency_key": "letter-length"},
            ),
            "conflict",
        )
        third = policy.add_item(
            "writing", {"expected_version": 2, "label": "One page", "scope": "cv", "position": 0}
        )
        assert [(item["label"], item["position"]) for item in third["section"]["items"]] == [
            ("One page", 0),
            ("Weaknesses", 1),
            ("Letter length", 2),
        ]
        # The other sections did not move.
        assert versions(policy) == {"decision": 0, "eligibility": 0, "writing": 3, "facts": 0}
        ids = [item["id"] for item in third["section"]["items"]]
        refused(
            lambda: policy.reorder_items(
                "writing", {"expected_version": 3, "item_ids": ids[:2] + ids[:1]}
            ),
            "policy_order",
            422,
        )
        same = policy.reorder_items("writing", {"expected_version": 3, "item_ids": ids})
        assert same["section"]["version"] == 3
        reordered = policy.reorder_items(
            "writing", {"expected_version": 3, "item_ids": list(reversed(ids))}
        )
        assert reordered["section"]["version"] == 4
        assert [item["label"] for item in reordered["section"]["items"]] == [
            "Letter length",
            "Weaknesses",
            "One page",
        ]
        refused(lambda: policy.remove_item(ids[1], 3), "conflict")
        removed = policy.remove_item(ids[1], 4)
        assert removed["deleted"] and removed["section"]["version"] == 5
        assert [item["position"] for item in removed["section"]["items"]] == [0, 1]
        with pytest.raises(DomainError, match="Policy item was not found"):
            policy.remove_item(ids[1], 5)
        assert policy.get_policy("writing") == policy.get_policy()["sections"][2]
        refused(lambda: policy.get_policy("other"), "not_found", 404)


def test_an_item_moves_between_sections_with_both_versions(services):
    _, policy = services
    with acting_as(OWNER):
        fact = policy.add_item("facts", {"expected_version": 0, "label": "British spelling"})[
            "item"
        ]
        policy.add_item("facts", {"expected_version": 1, "label": "Notice period", "value": 30})
        refused(
            lambda: policy.move_item(
                fact["id"], {"expected_version": 2, "section": "writing", "target_version": 4}
            ),
            "conflict",
        )
        refused(
            lambda: policy.move_item(
                fact["id"], {"expected_version": 2, "section": "facts", "target_version": 2}
            ),
            "policy_move",
            422,
        )
        moved = policy.move_item(
            fact["id"], {"expected_version": 2, "section": "writing", "target_version": 0}
        )
        assert (moved["item"]["section"], moved["item"]["scope"]) == ("writing", "all")
        assert moved["item"]["confirmed"] and moved["section"]["version"] == 1
        assert moved["from"]["version"] == 3
        assert [item["position"] for item in moved["from"]["items"]] == [0]
        back = policy.move_item(
            fact["id"], {"expected_version": 1, "section": "decision", "target_version": 0}
        )
        assert back["item"]["scope"] is None
        ruled = policy.update_item(fact["id"], {"expected_version": 1, "rule": RULE})
        refused(
            lambda: policy.move_item(
                fact["id"],
                {
                    "expected_version": ruled["section"]["version"],
                    "section": "facts",
                    "target_version": 3,
                },
            ),
            "policy_rule",
            422,
        )


def test_only_the_owner_confirms_and_an_agent_change_is_a_proposal(services):
    _, policy = services
    with acting_as(AGENT):
        proposed = policy.add_item(
            "eligibility",
            {"expected_version": 0, "label": "Relocation", "statement": "Not outside Europe."},
        )["item"]
        assert not proposed["confirmed"] and proposed["confirmed_at"] is None
        assert proposed["confirmed_by"] is None and proposed["created_by"]["token_kind"] == "agent"
        refused(
            lambda: policy.confirm_item(proposed["id"], {"expected_version": 1}), "forbidden", 403
        )
    for actor, version in ((OWNER, 1), (OWNER_TOKEN, 2)):
        with acting_as(actor):
            refused(
                lambda: policy.confirm_item(proposed["id"], {"expected_version": 0}), "conflict"
            )
            confirmed = policy.confirm_item(proposed["id"], {"expected_version": version})
    # The second confirmation changed nothing: one version, the first confirmer.
    assert confirmed["section"]["version"] == 2
    item = confirmed["item"]
    assert item["confirmed"] and item["confirmed_by"]["kind"] == "owner"
    assert item["updated_by"]["token_kind"] == "agent"
    with acting_as(AGENT):
        # A note is not content: the confirmation stays.
        noted = policy.update_item(proposed["id"], {"expected_version": 2, "note": "From a call."})
        assert noted["item"]["confirmed"] and noted["section"]["version"] == 3
        unchanged = policy.update_item(
            proposed["id"], {"expected_version": 3, "note": "From a call."}
        )
        assert unchanged["section"]["version"] == 3
        changed = policy.update_item(
            proposed["id"], {"expected_version": 3, "statement": "Not outside Switzerland."}
        )
        assert not changed["item"]["confirmed"] and changed["item"]["confirmed_by"] is None
        assert changed["section"]["unconfirmed"] == 1
    with acting_as(OWNER_TOKEN):
        owned = policy.update_item(proposed["id"], {"expected_version": 4, "value": "2027-02"})
        assert owned["item"]["confirmed"] and owned["item"]["value_type"] == "text"
        assert owned["item"]["confirmed_by"]["token_kind"] == "owner"


def test_a_rule_is_validated_stays_off_and_only_the_owner_enables_it(services):
    _, policy = services
    with acting_as(AGENT):
        refused(
            lambda: policy.add_item("facts", {"expected_version": 0, "label": "L", "rule": RULE}),
            "policy_rule",
            422,
        )
        refused(
            lambda: policy.add_item(
                "decision", {"expected_version": 0, "label": "L", "enabled": True}
            ),
            "policy_rule",
            422,
        )
        refused(
            lambda: policy.add_item(
                "decision", {"expected_version": 0, "label": "L", "rule": RULE, "enabled": True}
            ),
            "forbidden",
            403,
        )
        item = policy.add_item(
            "decision", {"expected_version": 0, "label": "Languages outside my list", "rule": RULE}
        )["item"]
        assert item["rule"] == RULE and item["enabled"] is False
        refused(
            lambda: policy.update_item(item["id"], {"expected_version": 1, "enabled": True}),
            "forbidden",
            403,
        )
    for rule, message in (
        ({**RULE, "signal": "salary"}, "signal"),
        ({**RULE, "condition": {"operator": "at_least", "value": 1}}, "allows the operators"),
        ({**RULE, "condition": {"operator": "in", "value": "English"}}, "list value"),
        ({**RULE, "action": "merge"}, "action"),
        (
            {
                "signal": "likely_duplicate",
                "condition": {"operator": "at_least", "value": 2},
                "action": "flag",
            },
            "between 0 and 1",
        ),
    ):
        with pytest.raises(ValidationError, match=message):
            PolicyItemCreate(expected_version=0, label="L", rule=rule)
    with acting_as(OWNER):
        enabled = policy.update_item(item["id"], {"expected_version": 1, "enabled": True})
        assert enabled["item"]["enabled"] and enabled["item"]["confirmed"] is False
        confirmed = policy.confirm_item(item["id"], {"expected_version": 2})
        assert confirmed["item"]["confirmed"] and confirmed["item"]["enabled"]
    with acting_as(AGENT):
        # An agent may switch a rule off; changing it makes it a proposal that is off.
        rewritten = policy.update_item(
            item["id"],
            {
                "expected_version": 3,
                "rule": {
                    "signal": "no_longer_listed",
                    "condition": {"operator": "is", "value": True},
                    "action": "flag",
                },
            },
        )
        assert rewritten["item"]["enabled"] is False and not rewritten["item"]["confirmed"]
    with acting_as(OWNER):
        cleared = policy.update_item(item["id"], {"expected_version": 4, "rule": None})
        assert cleared["item"]["rule"] is None and cleared["item"]["enabled"] is False
    # Nothing applies a rule yet: the registry says so.
    assert policy.get_policy()["signals_applied"] is False


def test_values_are_small_and_typed(services):
    _, policy = services
    cases = {
        "text": ("  Valid to 2028 ", "Valid to 2028", "text"),
        "number": (45, 45, "number"),
        "boolean": (False, False, "boolean"),
        "list": ([" Zurich ", "Basel"], ["Zurich", "Basel"], "list"),
    }
    with acting_as(OWNER):
        version = 0
        for label, (given, stored, kind) in cases.items():
            item = policy.add_item(
                "facts", {"expected_version": version, "label": label, "value": given}
            )["item"]
            version += 1
            assert (item["value"], item["value_type"]) == (stored, kind)
        dated = policy.add_item(
            "facts",
            {
                "expected_version": version,
                "label": "Start",
                "value": "2027-02-01",
                "value_type": "date",
            },
        )["item"]
        assert dated["value_type"] == "date"
        cleared = policy.update_item(dated["id"], {"expected_version": version + 1, "value": None})
        assert (cleared["item"]["value"], cleared["item"]["value_type"]) == (None, None)
    for value, kind in (
        ({"nested": 1}, None),
        ("", None),
        ("x" * 2001, None),
        ([], None),
        (["a", 1], None),
        (["x"] * 51, None),
        (float("nan"), None),
        ("tomorrow", "date"),
        ("2027-13", "date"),
        (1, "text"),
        (True, "number"),
        ({"a": 1}, "structured"),
    ):
        with pytest.raises(ValidationError):
            PolicyItemCreate(expected_version=0, label="L", value=value, value_type=kind)
    with pytest.raises(ValidationError, match="needs a value"):
        PolicyItemUpdate(expected_version=0, value_type="text")
    with pytest.raises(ValidationError, match="Omit label"):
        PolicyItemUpdate(expected_version=0, label=None)
    with pytest.raises(ValidationError):
        PolicyItemCreate(expected_version=0, label="   ")
    with acting_as(OWNER):
        refused(
            lambda: policy.add_item("facts", {"expected_version": 5, "label": "L", "scope": "cv"}),
            "policy_scope",
            422,
        )


def test_every_write_leaves_an_attributed_event_without_statement_text(services):
    workspace, policy = services
    secret = "Never mention the synthetic secret."
    with acting_as(AGENT):
        item = policy.add_item(
            "writing", {"expected_version": 0, "label": "Secret label", "statement": secret}
        )["item"]
        policy.update_item(item["id"], {"expected_version": 1, "statement": secret + " Ever."})
    with acting_as(OWNER):
        policy.confirm_item(item["id"], {"expected_version": 2})
        other = policy.add_item("writing", {"expected_version": 3, "label": "Second"})["item"]
        policy.reorder_items(
            "writing", {"expected_version": 4, "item_ids": [other["id"], item["id"]]}
        )
        policy.move_item(
            item["id"], {"expected_version": 5, "section": "facts", "target_version": 0}
        )
        policy.remove_item(item["id"], 1)
    events = workspace.db.all(
        "SELECT kind,payload,subject_type,subject_id,actor_kind,actor_token_kind FROM events "
        "WHERE kind LIKE 'policy%' ORDER BY rowid"
    )
    assert [event["kind"] for event in events] == [
        "policy_item_added",
        "policy_item_updated",
        "policy_item_confirmed",
        "policy_item_added",
        "policy_reordered",
        "policy_item_moved",
        "policy_item_removed",
    ]
    payloads = [json.loads(event["payload"]) for event in events]
    assert payloads[0] == {
        "item_id": item["id"],
        "section": "writing",
        "version": 1,
        "confirmed": False,
    }
    assert payloads[1] == {
        "item_id": item["id"],
        "section": "writing",
        "version": 2,
        "fields": ["statement"],
        "confirmed": False,
    }
    assert payloads[4] == {"section": "writing", "version": 5}
    assert payloads[5] == {
        "item_id": item["id"],
        "section": "facts",
        "version": 1,
        "from_section": "writing",
        "from_version": 6,
    }
    assert (events[4]["subject_type"], events[4]["subject_id"]) == ("policy", "writing")
    assert all(
        (event["subject_type"], event["subject_id"]) == ("policy_item", item["id"])
        for event in events[:3]
    )
    assert [event["actor_token_kind"] for event in events[:2]] == ["agent", "agent"]
    assert events[2]["actor_kind"] == "owner"
    text = json.dumps(payloads)
    assert "secret" not in text.lower() and "Second" not in text


def tool(client, token, name, arguments=None):
    response = client.post(
        "/mcp",
        headers={**MCP_HEADERS, "Authorization": "Bearer " + token["token"]},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        },
    )
    result = response.json()["result"]
    if result.get("isError"):
        return None, json.loads(result["content"][0]["text"])["error"]
    return result.get("structuredContent") or json.loads(result["content"][0]["text"]), None


def test_rest_mcp_and_the_dashboard_session_manage_the_same_items(tmp_path):
    app = create_app(tmp_path / "interfaces.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    agent = app.state.auth.create_token("Synthetic agent", "agent")
    owner_token = app.state.auth.create_token("Synthetic owner token")
    owner = TestClient(app)
    session = owner.post("/api/v1/auth/login", json={"password": "synthetic-password"})
    owner.headers["X-CSRF-Token"] = session.json()["csrf_token"]
    headers = {"Authorization": "Bearer " + agent["token"]}
    with TestClient(app, base_url="http://localhost:8080") as client:
        created = owner.post(
            "/api/v1/policy/eligibility/items",
            json={
                "expected_version": 0,
                "label": "Work authorization",
                "statement": "EU citizen.",
                "value": "2028-06-30",
                "value_type": "date",
            },
        )
        assert created.status_code == 201 and created.json()["item"]["confirmed"]
        proposed, error = tool(
            client,
            agent,
            "policy_add",
            {
                "section": "decision",
                "value": {"expected_version": 0, "label": "Languages", "rule": RULE},
            },
        )
        assert error is None and proposed["item"]["confirmed"] is False
        item_id = proposed["item"]["id"]
        # The owner-only steps are refused for the agent alike on both interfaces.
        body = {"expected_version": 1}
        over_rest = client.post(
            f"/api/v1/policy/items/{item_id}/confirm", json=body, headers=headers
        )
        _, over_mcp = tool(client, agent, "policy_confirm", {"item_id": item_id, "value": body})
        assert over_rest.status_code == 403 == over_mcp["status"]
        assert over_rest.json()["error"]["code"] == over_mcp["code"] == "forbidden"
        assert over_rest.json()["error"]["details"] == over_mcp["details"]
        enable = {"expected_version": 1, "enabled": True}
        over_rest = client.patch(f"/api/v1/policy/items/{item_id}", json=enable, headers=headers)
        _, over_mcp = tool(client, agent, "policy_update", {"item_id": item_id, "value": enable})
        assert over_rest.json()["error"]["code"] == over_mcp["code"] == "forbidden"
        # A stale version is the same structured conflict.
        stale = {"expected_version": 7, "note": "x"}
        over_rest = client.patch(f"/api/v1/policy/items/{item_id}", json=stale, headers=headers)
        _, over_mcp = tool(client, agent, "policy_update", {"item_id": item_id, "value": stale})
        assert over_rest.status_code == 409 == over_mcp["status"]
        assert over_rest.json()["error"]["code"] == over_mcp["code"] == "conflict"
        assert over_rest.json()["error"]["details"] == over_mcp["details"]
        assert over_mcp["details"] == {"current_version": 1, "section": "decision"}
        confirmed = owner.post(f"/api/v1/policy/items/{item_id}/confirm", json=body).json()
        assert confirmed["item"]["confirmed_by"]["label"] == "Owner (dashboard)"
        enabled, error = tool(
            client,
            owner_token,
            "policy_update",
            {"item_id": item_id, "value": {"expected_version": 2, "enabled": True}},
        )
        assert error is None and enabled["item"]["enabled"]
        for path, arguments in (
            ("/api/v1/policy", {}),
            ("/api/v1/policy/decision", {"section": "decision"}),
            ("/api/v1/policy/facts", {"section": "facts"}),
        ):
            over_mcp, error = tool(client, agent, "policy_get", arguments)
            assert error is None
            assert client.get(path, headers=headers).json() == over_mcp == owner.get(path).json()
        assert client.get("/api/v1/policy/other", headers=headers).status_code == 422
        moved, error = tool(
            client,
            agent,
            "policy_move",
            {
                "item_id": created.json()["item"]["id"],
                "value": {"expected_version": 1, "section": "facts", "target_version": 0},
            },
        )
        assert error is None and moved["item"]["section"] == "facts"
        ordered, error = tool(
            client,
            agent,
            "policy_reorder",
            {"section": "decision", "value": {"expected_version": 3, "item_ids": [item_id]}},
        )
        assert error is None and ordered["section"]["version"] == 3
        gone = client.delete(
            f"/api/v1/policy/items/{item_id}", params={"expected_version": 3}, headers=headers
        )
        assert gone.status_code == 200 and gone.json()["section"]["items"] == []
        _, error = tool(client, agent, "policy_remove", {"item_id": item_id, "expected_version": 4})
        assert error["code"] == "not_found"
        # The record export carries the policy; the change log names the items.
        exported = owner.get("/api/v1/export").json()
        assert [row["section"] for row in exported["policy_sections"]] == list(SECTIONS)
        assert [(row["label"], row["value"]) for row in exported["policy_items"]] == [
            ("Work authorization", "2028-06-30")
        ]
        changes = owner.get("/api/v1/events", params={"subject_type": "policy_item"}).json()
        assert changes["total"] == 6
        labels = {item["subject"]["label"] for item in changes["items"]}
        assert "Work authorization" in labels


def prepared(workspace, application_id):
    return DocumentService(workspace).prepare_context(ContextCreate(application_id=application_id))


def test_a_context_freezes_the_sections_as_shared_parts(tmp_path):
    workspace, _, _, _, applications = seed(tmp_path / "frozen.sqlite")
    policy = PolicyService(workspace)
    with acting_as(OWNER):
        policy.add_item(
            "writing",
            {
                "expected_version": 0,
                "label": "Weaknesses",
                "statement": "Never volunteer weaknesses or missing skills. " * 6,
            },
        )
    with acting_as(AGENT):
        policy.add_item(
            "decision",
            {
                "expected_version": 0,
                "label": "Proposed rule",
                "statement": "Dismiss roles that need a language outside the list. " * 5,
                "rule": RULE,
            },
        )
    first = prepared(workspace, applications[0])
    frozen = first["payload"]["policy"]
    assert list(frozen) == sorted(SECTIONS)
    assert {name: section["version"] for name, section in frozen.items()} == {
        "decision": 1,
        "eligibility": 0,
        "writing": 1,
        "facts": 0,
    }
    proposal = frozen["decision"]["items"][0]
    assert proposal["confirmed"] is False and proposal["confirmed_at"] is None
    assert proposal["rule"] == RULE and proposal["enabled"] is False
    assert frozen["writing"]["items"][0]["confirmed"] is True
    assert set(proposal) == {
        "id",
        "label",
        "statement",
        "value",
        "value_type",
        "note",
        "scope",
        "rule",
        "enabled",
        "confirmed",
        "confirmed_at",
        "origin",
    }
    with workspace.db.connect() as conn:
        text = payload_text(conn, first["id"])
        assert hashlib.sha256(text.encode()).hexdigest() == first["signature"]
        inputs = conn.execute(
            "SELECT policy FROM context_inputs WHERE context_id=?", (first["id"],)
        ).fetchone()[0]
        assert json.loads(inputs) == {"decision": 1, "eligibility": 0, "writing": 1, "facts": 0}

        def section_parts():
            return conn.execute(
                "SELECT count(*) FROM snapshot_parts WHERE instr(content,'\"items\":[')=2"
            ).fetchone()[0]

        assert section_parts() == 2  # the two sections long enough to be shared
    second = prepared(workspace, applications[1])
    with acting_as(OWNER):
        policy.add_item("writing", {"expected_version": 1, "label": "One page", "scope": "cv"})
    third = prepared(workspace, applications[2])
    with workspace.db.connect() as conn:
        # The second context added no section part; the third only the changed section.
        assert section_parts() == 3
        assert json.loads(
            conn.execute(
                "SELECT policy FROM context_inputs WHERE context_id=?", (third["id"],)
            ).fetchone()[0]
        ) == {"decision": 1, "eligibility": 0, "writing": 2, "facts": 0}
    assert second["payload"]["policy"] == frozen
    assert [item["label"] for item in third["payload"]["policy"]["writing"]["items"]] == [
        "Weaknesses",
        "One page",
    ]
    # Earlier contexts stay as they were frozen.
    assert DocumentService(workspace).get_context(first["id"]) == first
    # Deriving the summaries again reads the same versions from the payload.
    with workspace.db.transaction() as conn:
        before = [
            tuple(row) for row in conn.execute("SELECT * FROM context_inputs ORDER BY context_id")
        ]
        conn.execute("DELETE FROM context_inputs")
    Workspace(workspace.db.path)
    with workspace.db.connect() as conn:
        assert [
            tuple(row) for row in conn.execute("SELECT * FROM context_inputs ORDER BY context_id")
        ] == before


def schema_nine_workspace(path):
    """A schema 9 file with a free-form Profile, claim metadata and released contexts."""
    workspace, knowledge, claims, _, applications = seed(path)
    career = CareerService(workspace)
    career.update_profile(
        ProfileUpdate(
            expected_version=career.get_profile()["version"],
            preferences="Remote first.\nNo consultancies — “synthetic”.",
            metadata=METADATA,
        )
    )
    exact = {
        claims[0]: {"default_in_cv": True, "role": "core", "group": "Data pipelines", "x": 1},
        claims[1]: {"default_in_cv": "yes", "role": "primary", "group": ["a"]},
        claims[2]: {"role": "bench", "selection": {"role": "core"}},
        claims[3]: {"default_in_cv": 1, "group": "g" * 101},
    }
    with workspace.db.transaction() as conn:
        for claim_id, metadata in exact.items():
            conn.execute(
                "UPDATE claims SET metadata=? WHERE id=?", (json.dumps(metadata), claim_id)
            )
    del workspace, career
    make_schema_eight(path)
    legacy_prepare_context(path, applications[0], key="first-key")
    legacy_prepare_context(path, applications[1], knowledge_ids=knowledge[:2])
    legacy_prepare_context(path, applications[2], note="Synthetic note ✓")
    # The released 8 -> 9 step alone, as 0.18 ran it.
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        MIGRATIONS[8](conn)
        conn.execute("PRAGMA user_version=9")
        conn.commit()
        conn.execute("PRAGMA journal_mode=DELETE")
    return claims, applications


PRESERVED = ("settings", "knowledge", "claims", "templates", "contexts", "context_parts", "events")


def rows_of(conn, table):
    added = SCHEMA_TEN_COLUMNS.get(table, ())
    names = [f'"{row[0]}"' for row in columns(conn, table) if row[0] not in added]
    return conn.execute(f"SELECT {','.join(names)} FROM {table} ORDER BY 1,2").fetchall()


def test_schema_nine_upgrade_copies_the_profile_and_touches_no_existing_row(tmp_path):
    path = tmp_path / "schema9.sqlite"
    claims, applications = schema_nine_workspace(path)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 9
        assert not {"policy_items", "policy_sections"} & table_names(conn)
        assert "role" not in {row[0] for row in columns(conn, "claims")}
        before = {table: rows_of(conn, table) for table in PRESERVED}
        payloads = {
            row[0]: (payload_text(conn, row[0]), row[1])
            for row in conn.execute("SELECT id,signature FROM contexts")
        }
        parts = conn.execute("SELECT * FROM snapshot_parts ORDER BY id").fetchall()
    assert len(payloads) == 3 and len(before["claims"]) == 24

    workspace = Workspace(path)
    fresh = Database(tmp_path / "fresh.sqlite")
    with sqlite3.connect(path) as conn, sqlite3.connect(fresh.path) as reference:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 10
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert table_names(conn) == table_names(reference)
        assert index_names(conn) == index_names(reference)
        for table in table_names(reference):
            if not table.startswith("jobs_fts"):
                assert sorted(columns(conn, table)) == sorted(columns(reference, table)), table
        # Every existing row, and every frozen context, is what it was.
        for table in PRESERVED:
            assert rows_of(conn, table) == before[table], table
        assert conn.execute("SELECT * FROM snapshot_parts ORDER BY id").fetchall() == parts
        for context_id, (text, signature) in payloads.items():
            assert payload_text(conn, context_id) == text
            assert hashlib.sha256(text.encode()).hexdigest() == signature
            assert "policy" not in json.loads(text)
        # A context from before the policy has no section versions.
        assert conn.execute("SELECT policy FROM context_inputs").fetchall() == [(None,)] * 3
        typed = {
            row[0]: row[1:]
            for row in conn.execute('SELECT id,default_in_cv,role,"group" FROM claims')
        }
    # Only a key with the field's name and a valid value of the field is copied.
    assert typed[claims[0]] == (1, "core", "Data pipelines")
    assert typed[claims[1]] == (0, "supporting", "")
    assert typed[claims[2]] == (0, "bench", "")
    assert typed[claims[3]] == (0, "supporting", "")
    assert all(
        value == (0, "supporting", "") for key, value in typed.items() if key not in claims[:4]
    )

    career, policy = CareerService(workspace), PolicyService(workspace)
    profile = career.get_profile()
    # Nothing left the Profile.
    assert profile["metadata"] == METADATA and profile["roles"] == "Backend engineer"
    assert profile["preferences"].startswith("Remote first.")
    sections = {section["section"]: section for section in policy.get_policy()["sections"]}
    assert {name: section["version"] for name, section in sections.items()} == {
        "decision": 1,
        "eligibility": 0,
        "writing": 0,
        "facts": 1,
    }
    facts = sections["facts"]["items"]
    # One item per key, in the order the Profile stores them.
    assert [item["origin"]["key"] for item in facts] == sorted(METADATA)
    assert [item["position"] for item in facts] == list(range(len(METADATA)))
    assert {item["origin"]["key"]: item["value"] for item in facts} == METADATA
    assert [item["label"] for item in facts][:2] == ["Interview availability", "Decision policy"]
    assert {item["origin"]["key"]: item["value_type"] for item in facts} == {
        "decision_policy": "structured",
        "work_authorization": "text",
        "notice_period_days": "number",
        "open_to_relocation": "boolean",
        "salary": "number",
        "languages": "structured",
        "unset": "structured",
        "Interview-availability": "structured",
    }
    decision = sections["decision"]["items"]
    assert [(item["label"], item["statement"]) for item in decision] == [
        ("Preferences", profile["preferences"]),
        ("Target roles", profile["roles"]),
    ]
    assert [item["origin"]["source"] for item in decision] == [
        "profile_preferences",
        "profile_roles",
    ]
    for item in facts + decision:
        assert item["confirmed"] is False and item["confirmed_by"] is None
        assert item["created_by"]["kind"] == "system"
        assert item["origin"]["note"].startswith("Copied from Profile ")
        assert item["origin"]["note"].endswith(" in 0.19")
    assert sections["facts"]["unconfirmed"] == len(METADATA)

    # A structured value is kept until someone sorts it: other fields change around it,
    # a typed value replaces it, and it cannot be written again.
    structured = facts[1]
    with acting_as(AGENT):
        labelled = policy.update_item(
            structured["id"], {"expected_version": 1, "label": "Decision policy (old)"}
        )["item"]
        assert labelled["value"] == METADATA["decision_policy"]
        assert labelled["value_type"] == "structured"
        with pytest.raises(ValidationError):
            policy.update_item(
                structured["id"],
                {"expected_version": 2, "value": {"a": 1}, "value_type": "structured"},
            )
    with acting_as(OWNER):
        sorted_item = policy.update_item(
            structured["id"], {"expected_version": 2, "value": ["backend"], "value_type": "list"}
        )["item"]
        assert sorted_item["confirmed"] and sorted_item["value_type"] == "list"
        assert sorted_item["origin"]["key"] == "decision_policy"
    # A new context freezes the copied items as unconfirmed.
    context = prepared(workspace, applications[0])
    frozen = context["payload"]["policy"]["facts"]["items"]
    assert [item["confirmed"] for item in frozen] == [False, True] + [False] * (len(METADATA) - 2)
    assert frozen[0]["origin"]["source"] == "profile_metadata"
    assert frozen[0]["value"] == METADATA["Interview-availability"]
    # Opening again copies nothing twice.
    again = PolicyService(Workspace(path)).get_policy()
    assert [section["total"] for section in again["sections"]] == [2, 0, 0, len(METADATA)]


def test_an_older_backup_restores_through_the_same_step(tmp_path):
    source = tmp_path / "schema9.sqlite"
    schema_nine_workspace(source)
    original = source.read_bytes()
    target = Workspace(tmp_path / "live" / "workspace.sqlite")
    with acting_as(OWNER):
        PolicyService(target).add_item("facts", {"expected_version": 0, "label": "Replaced"})
    restore_database(target, source)
    assert source.read_bytes() == original
    restored = PolicyService(target).get_policy()
    assert [section["total"] for section in restored["sections"]] == [2, 0, 0, len(METADATA)]
    assert CareerService(target).get_profile()["metadata"] == METADATA
    # A current backup carries the policy as it is.
    with acting_as(OWNER):
        PolicyService(target).add_item("eligibility", {"expected_version": 0, "label": "Permit"})
    backup = tmp_path / "current.sqlite"
    target.db.backup(backup)
    other = Workspace(tmp_path / "other" / "workspace.sqlite")
    restore_database(other, backup)
    assert PolicyService(other).get_policy() == PolicyService(target).get_policy()


def test_a_profile_without_free_form_values_gets_an_empty_policy(tmp_path):
    path = tmp_path / "plain.sqlite"
    Workspace(path)
    CareerService(Workspace(path))
    make_schema_nine(path)
    policy = PolicyService(Workspace(path)).get_policy()
    assert all(section["version"] == 0 and not section["items"] for section in policy["sections"])


def test_claims_carry_typed_selection_fields(tmp_path):
    workspace = Workspace(tmp_path / "claims.sqlite")
    career = CareerService(workspace)
    entry = career.create_knowledge(KnowledgeCreate(kind="project", title="Synthetic entry"))
    plain = career.create_claim(ClaimCreate(knowledge_id=entry["id"], text="Built a pipeline."))
    assert (plain["default_in_cv"], plain["role"], plain["group"]) == (False, "supporting", "")
    core = career.create_claim(
        ClaimCreate(
            knowledge_id=entry["id"],
            text="Cut query time.",
            approved=True,
            default_in_cv=True,
            role="core",
            group="  Data pipelines ",
        )
    )
    assert (core["default_in_cv"], core["role"], core["group"]) == (True, "core", "Data pipelines")
    updated = career.update_claim(
        plain["id"], ClaimUpdate(expected_version=1, role="bench", default_in_cv=True)
    )
    assert (updated["role"], updated["default_in_cv"], updated["version"]) == ("bench", True, 2)
    assert (
        career.update_claim(plain["id"], ClaimUpdate(expected_version=2, role="bench"))["version"]
        == 2
    )
    event = workspace.db.one(
        "SELECT payload FROM events WHERE kind='claim_updated' ORDER BY rowid DESC LIMIT 1"
    )
    assert json.loads(event["payload"])["fields"] == ["default_in_cv", "role"]
    for value in ({"role": "primary"}, {"group": "g" * 101}, {"default_in_cv": None}):
        with pytest.raises(ValidationError):
            ClaimUpdate(expected_version=2, **value)
    for summary in (True, False):
        listed = career.list_claims(summary=summary)["items"]
        assert [(item["role"], item["default_in_cv"], item["group"]) for item in listed] == [
            ("bench", True, ""),
            ("core", True, "Data pipelines"),
        ]
    career.create_template(TemplateCreate(name="CV", tex="x"))
    job = workspace.ingest_job({"title": "Role", "company": "Example", "posting": "Build."})
    application = workspace.create_application({"job_id": job["id"]})
    frozen = prepared(workspace, application["id"])["payload"]["claims"]
    assert [(claim["role"], claim["default_in_cv"], claim["group"]) for claim in frozen] == [
        ("core", True, "Data pipelines")
    ]


def test_template_rules_hold_typed_statements_beside_limits_and_free_keys(tmp_path):
    career = CareerService(Workspace(tmp_path / "templates.sqlite"))
    template = career.create_template(
        TemplateCreate(
            name="CV",
            rules={
                "max_pages": 1,
                "engine": "lualatex",
                "statements": [
                    {"label": " Order ", "statement": " Experience first. "},
                    {"id": "links", "statement": "No links in bullets.", "scope": "experience"},
                ],
            },
        )
    )
    statements = template["rules"]["statements"]
    assert [item["position"] for item in statements] == [0, 1]
    assert statements[0]["label"] == "Order" and statements[0]["statement"] == "Experience first."
    assert len(statements[0]["id"]) == 32 and statements[0]["scope"] is None
    assert statements[1] == {
        "id": "links",
        "label": "",
        "statement": "No links in bullets.",
        "scope": "experience",
        "position": 1,
    }
    assert template["rules"]["engine"] == "lualatex" and template["rules"]["max_pages"] == 1
    # Sending the list back in another order keeps the ids and renumbers.
    updated = career.update_template(
        template["id"],
        TemplateUpdate(
            expected_version=1,
            rules={**template["rules"], "statements": list(reversed(statements))},
        ),
    )
    assert [(item["id"], item["position"]) for item in updated["rules"]["statements"]] == [
        ("links", 0),
        (statements[0]["id"], 1),
    ]
    for bad in (
        "text",
        [{"statement": ""}],
        [{"statement": "x", "extra": 1}],
        [{"id": "a", "statement": "x"}, {"id": "a", "statement": "y"}],
        [{"statement": "x", "scope": 3}],
        [{"statement": "x" * 4001}],
    ):
        with pytest.raises(ValidationError):
            TemplateCreate(name="CV", rules={"statements": bad})
