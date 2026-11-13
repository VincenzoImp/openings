"""One name and one argument shape per operation (#167), and the aliases kept until 0.23."""

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mcp.server.mcpserver.exceptions import ToolError

from openings.actors import OWNER, acting_as
from openings.app import create_app
from openings.career import ClaimCreate, KnowledgeCreate
from openings.documents import DocumentCreate, UploadReservation
from openings.interfaces import GUIDE_PATH, catalog, with_upgrade_tables
from openings.interfaces.registry import REMOVAL, deprecation

ROOT = Path(__file__).resolve().parents[2]
# Resources that name one record of the workspace, or a mass noun, stay singular.
SINGULAR = {
    "capabilities",
    "career",
    "collection",
    "insights",
    "instructions",
    "knowledge",
    "overview",
    "owner_password",
    "policy",
    "profile",
    "staleness",
    "timeline",
    "workspace",
}


async def call(mcp, name, arguments=None):
    result = await mcp.call_tool(name, arguments or {})
    return json.loads(result.content[0].text)


async def refused(mcp, name, arguments):
    with pytest.raises(ToolError) as error:
        await mcp.call_tool(name, arguments)
    return json.loads(str(error.value))["error"]


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / "names.sqlite", start_worker=False)


def seed(app):
    """A job with a note and an application, a Career entry and a claim."""
    workspace, career = app.state.workspace, app.state.career
    with acting_as(OWNER):
        job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build APIs."})
        application = workspace.create_application({"job_id": job["id"]})
        note = workspace.add_note(job["id"], {"body": "Synthetic note."})
        entry = career.create_knowledge(
            KnowledgeCreate(title="Synthetic project", narrative="Built it.")
        )
        claim = career.create_claim(ClaimCreate(knowledge_id=entry["id"], text="Built a thing."))
    return {"job": job, "application": application, "note": note, "entry": entry, "claim": claim}


def test_every_tool_is_named_from_its_declaration():
    """`<resource>_<verb>`, plural resources, no name given by hand."""
    operations, _, _ = catalog()
    names = [operation.canonical_name for operation in operations if operation.tool]
    assert len(names) == len(set(names))
    for operation in operations:
        assert operation.resource in SINGULAR or operation.resource.endswith("s"), operation.id
        assert not hasattr(operation.tool, "name"), operation.id
    aliases = [alias.name for operation in operations for alias in operation.alias_entries]
    assert len(aliases) == len(set(aliases)) and not set(aliases) & set(names)


async def test_every_alias_is_its_operation_under_an_earlier_name(app):
    """Same handler (or, for an earlier shape, the same call), annotations and a deprecation."""
    operations, _, _ = catalog()
    manager = app.state.mcp._tool_manager
    reshaped = set()
    for operation in operations:
        tool = manager.get_tool(operation.canonical_name)
        for alias in operation.alias_entries:
            registered = manager.get_tool(alias.name)
            assert registered.description.startswith(deprecation(operation.canonical_name))
            assert registered.description.endswith(tool.description)
            assert registered.annotations == tool.annotations
            if alias.params is None:
                assert registered.fn is tool.fn, alias.name
                assert registered.parameters == tool.parameters
            else:
                reshaped.add(alias.name)
    # The aliases that keep the arguments they took before 0.22, tested below.
    assert reshaped == {"applications_staleness", "note_delete", "skill_get"}
    assert deprecation("jobs_get") == f"Deprecated alias of jobs_get; removed in {REMOVAL}."


async def test_aliases_return_what_their_tools_return(app):
    data = seed(app)
    mcp = app.state.mcp
    job_id, application_id = data["job"]["id"], data["application"]["id"]
    same_input = {
        "job_get": ("jobs_get", {"job_id": job_id}),
        "jobs_search": ("jobs_list", {"value": {"queue": "inbox"}}),
        "note_get": ("notes_get", {"note_id": data["note"]["id"]}),
        "application_get": ("applications_get", {"application_id": application_id}),
        "application_history": ("applications_history", {"application_id": application_id}),
        "application_staleness": ("staleness_get", {"application_id": application_id}),
        "career_get_profile": ("profile_get", {}),
        "collection_yield": ("sources_yield", {"value": {"min_sample": 1}}),
    }
    for alias, (name, arguments) in same_input.items():
        assert await call(mcp, alias, arguments) == await call(mcp, name, arguments), alias
    # Aliases that keep their earlier, flat arguments.
    assert await call(
        mcp, "applications_staleness", {"status": "all", "stale_only": False, "limit": 5}
    ) == await call(
        mcp, "staleness_list", {"value": {"status": "all", "stale_only": False, "limit": 5}}
    )
    assert await call(
        mcp, "skill_get", {"name": "openings-workspace", "local_notes": False}
    ) == await call(
        mcp, "skills_get", {"name": "openings-workspace", "value": {"local_notes": False}}
    )
    # A write through an alias is the same operation.
    triaged = await call(
        mcp,
        "job_triage",
        {
            "job_id": job_id,
            "value": {
                "triage": "saved",
                "expected_version": (await call(mcp, "jobs_get", {"job_id": job_id}))["version"],
            },
        },
    )
    assert triaged["triage"] == "saved"
    # note_delete took no version; notes_delete requires it.
    assert (await refused(mcp, "notes_delete", {"note_id": data["note"]["id"]}))["code"] == (
        "validation"
    )
    assert await call(mcp, "note_delete", {"note_id": data["note"]["id"]}) == {"deleted": True}


async def test_tools_that_took_flat_arguments_still_accept_them_beside_value(app):
    data = seed(app)
    mcp = app.state.mcp
    flat = await call(mcp, "knowledge_list", {"q": "Synthetic", "summary": False})
    assert flat == await call(
        mcp, "knowledge_list", {"value": {"q": "Synthetic", "summary": False}}
    )
    assert flat["items"][0]["narrative"] == "Built it."
    assert await call(mcp, "claims_list", {"knowledge_id": data["entry"]["id"]}) == await call(
        mcp, "claims_list", {"value": {"knowledge_id": data["entry"]["id"]}}
    )
    error = await refused(mcp, "documents_list", {"limit": 5, "value": {"limit": 5}})
    assert error["code"] == "validation" and error["details"][0]["field"] == ["limit"]
    operations, _, _ = catalog()
    tools = {tool.name: tool for tool in await mcp.list_tools()}
    for operation in operations:
        if operation.tool and operation.tool.legacy:
            properties = tools[operation.canonical_name].input_schema["properties"]
            assert "value" in properties
            for name in operation.tool.legacy:
                assert REMOVAL in properties[name]["description"], (operation.id, name)


async def test_lists_return_summaries_by_default_with_limit_offset_and_total(app):
    mcp = app.state.mcp
    data = seed(app)
    lists = [tool.name for tool in await mcp.list_tools() if tool.name.endswith("_list")]
    # Bounded by one job, one application or the installation: every item and a total.
    bounded = {
        "notes_list": {"job_id": data["job"]["id"]},
        "responses_list": {"application_id": data["application"]["id"]},
        "providers_list": {},
        "skills_list": {},
        "tokens_list": {},
    }
    for name in lists:
        if name in bounded:
            assert "total" in await call(mcp, name, bounded[name]), name
            continue
        result = await call(mcp, name, {"value": {"limit": 7, "offset": 0}})
        assert (result["limit"], result["offset"]) == (7, 0), name
        assert "total" in result and "items" in result, name
    for name in ("knowledge_list", "claims_list", "templates_list", "contexts_list", "files_list"):
        schema = next(tool for tool in await mcp.list_tools() if tool.name == name).input_schema
        query = next(iter(schema["$defs"].values()))
        assert query["properties"]["summary"]["default"] is True, name
    assert "narrative" not in (await call(mcp, "knowledge_list"))["items"][0]


async def test_every_delete_takes_expected_version(app):
    operations, _, _ = catalog()
    tools = {tool.name: tool for tool in await app.state.mcp.list_tools()}
    deletes = [
        operation
        for operation in operations
        if any(route.method == "DELETE" and not route.custom for route in operation.rest)
    ]
    assert {operation.id for operation in deletes} >= {"notes.delete", "files.delete"}
    for operation in deletes:
        if operation.id == "tokens.revoke":
            continue  # a token has no version: revoking is not a versioned delete
        schema = tools[operation.canonical_name].input_schema["properties"]
        assert "expected_version" in schema, operation.id


def test_notes_revisions_and_files_are_deleted_with_their_version(app):
    data = seed(app)
    documents = app.state.documents
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic owner token")["token"]
    with TestClient(app, base_url="http://localhost:8080") as client:
        client.headers["Authorization"] = "Bearer " + token
        note = data["note"]
        stale = client.delete(f"/api/v1/notes/{note['id']}?expected_version=9")
        assert stale.status_code == 409
        assert stale.json()["error"]["details"] == {"current_version": note["version"]}
        deleted = client.delete(f"/api/v1/notes/{note['id']}?expected_version={note['version']}")
        assert deleted.status_code == 200
        # Without a version: accepted until 0.23, deprecated.
        other = app.state.workspace.add_note(data["job"]["id"], {"body": "Another note."})
        assert client.delete(f"/api/v1/notes/{other['id']}").status_code == 200

        revision = documents.create_document(
            DocumentCreate(application_id=data["application"]["id"], kind="other", content={"a": 1})
        )
        assert (
            client.delete(f"/api/v1/documents/{revision['id']}?expected_version=2").json()["error"][
                "code"
            ]
            == "conflict"
        )
        assert (
            client.delete(
                f"/api/v1/documents/{revision['id']}?expected_version={revision['version']}"
            ).status_code
            == 200
        )

        content = b"Synthetic asset."
        grant = documents.reserve_upload(
            UploadReservation(
                owner_type="knowledge",
                owner_id=data["entry"]["id"],
                name="asset.txt",
                size=len(content),
                media_type="text/plain",
            )
        )
        stored = client.put(grant["url"], headers=grant["headers"], content=content).json()
        assert documents.get_file(stored["id"])["version"] == 1
        assert client.delete(f"/api/v1/files/{stored['id']}?expected_version=2").status_code == 409
        assert client.delete(f"/api/v1/files/{stored['id']}?expected_version=1").status_code == 200


async def test_every_create_accepts_an_idempotency_key(app):
    operations, _, _ = catalog()
    tools = {tool.name: tool for tool in await app.state.mcp.list_tools()}
    creates = [
        operation
        for operation in operations
        if operation.verb in {"create", "add", "ask", "start"} and operation.tool
    ]
    assert len(creates) == 15
    for operation in creates:
        schema = tools[operation.canonical_name].input_schema
        body = schema["$defs"][schema["properties"]["value"]["$ref"].rsplit("/", 1)[1]]
        assert "idempotency_key" in body["properties"], operation.id


async def test_a_retried_create_returns_its_record_and_a_reused_key_is_refused(app):
    data = seed(app)
    mcp = app.state.mcp
    job_id, entry_id = data["job"]["id"], data["entry"]["id"]
    # Each create: its request, and a change to it that a reused key refuses.
    requests = {
        "jobs_create": ({"title": "Pasted role", "posting": "Pasted text."}, {"title": "Other"}),
        "notes_create": ({"body": "Retried note."}, {"body": "Other"}),
        "knowledge_create": ({"title": "Retried entry"}, {"title": "Other"}),
        "claims_create": ({"knowledge_id": entry_id, "text": "Retried claim."}, {"text": "Other"}),
        "templates_create": ({"name": "Retried template"}, {"name": "Other"}),
        "documents_create": (
            {"application_id": data["application"]["id"], "kind": "other"},
            {"title": "Other"},
        ),
        "sources_create": (
            {
                "name": "Retried search",
                "kind": "jobspy",
                "config": {"query": "engineer", "providers": ["linkedin"]},
            },
            {"name": "Other"},
        ),
        "tokens_create": ({"name": "Retried token", "kind": "agent"}, {"name": "Other"}),
    }
    for name, (body, change) in requests.items():
        arguments = {"job_id": job_id} if name == "notes_create" else {}

        async def create(fields, key, name=name, arguments=arguments):
            return await call(mcp, name, {**arguments, "value": {**fields, "idempotency_key": key}})

        first = await create(body, "k1")
        again = await create(body, "k1")
        assert again["id"] == first["id"], name
        # Another key creates another record (with other content: two revisions with
        # the same content are one revision even without a key).
        assert (await create({**body, **change}, "k2"))["id"] != first["id"], name
        error = await refused(
            mcp, name, {**arguments, "value": {**body, **change, "idempotency_key": "k1"}}
        )
        assert error["code"] == "conflict", name
        if name == "jobs_create":
            assert first["created"] is True and again["created"] is False
        if name == "tokens_create":
            assert first["token"] and again["token"] is None
    # A key whose record is gone is free again.
    note = await call(
        mcp, "notes_create", {"job_id": job_id, "value": {"body": "Gone.", "idempotency_key": "g"}}
    )
    await call(mcp, "notes_delete", {"note_id": note["id"], "expected_version": note["version"]})
    again = await call(
        mcp, "notes_create", {"job_id": job_id, "value": {"body": "Gone.", "idempotency_key": "g"}}
    )
    assert again["id"] != note["id"]


def deprecated_names():
    operations, _, _ = catalog()
    return {alias.name for operation in operations for alias in operation.alias_entries}


async def test_shipped_skills_docs_and_descriptions_use_no_deprecated_name(app):
    """The upgrade guide maps old names; the accepted proposal records the earlier state."""
    pattern = re.compile(r"(?<![\w{.-])(" + "|".join(sorted(deprecated_names())) + r")(?!\w)")
    exempt = {"docs/user/upgrading-0.22.md", "docs/developer/proposal-redesign.md"}
    files = [
        *ROOT.glob("skills/**/*.md"),
        *ROOT.glob("docs/**/*.md"),
        *ROOT.glob("examples/**/*.md"),
        ROOT / "README.md",
    ]
    found = {
        str(path.relative_to(ROOT)): sorted(set(pattern.findall(path.read_text())))
        for path in files
        if str(path.relative_to(ROOT)) not in exempt
    }
    assert not {path: names for path, names in found.items() if names}
    names = deprecated_names()
    for tool in await app.state.mcp.list_tools():
        if tool.name not in names:
            assert not pattern.findall(tool.description or ""), tool.name
    for prompt in await app.state.mcp.list_prompts():
        assert not pattern.findall(prompt.description or ""), prompt.name


def test_the_upgrade_guide_lists_every_alias_from_the_declarations():
    guide = (ROOT / GUIDE_PATH).read_text()
    assert guide == with_upgrade_tables(guide), "Run `uv run python scripts/inventory.py`."
    for name in deprecated_names():
        assert f"| `{name}` |" in guide
