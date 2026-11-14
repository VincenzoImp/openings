"""The OpenAPI document is valid and describes every operation completely."""

import inspect
import json

from openapi_spec_validator import validate
from pydantic import BaseModel

from openings.interfaces import OPERATIONS
from openings.openapi import EXAMPLES, main


def test_the_printed_schema_validates_and_documents_every_operation(capsys):
    # `python -m openings.openapi` (api:check) prints the schema without a server.
    main()
    schema = json.loads(capsys.readouterr().out)
    validate(schema)
    assert schema["paths"]["/api/v1/jobs"]["get"]["operationId"] == "jobs_list"
    assert schema["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"
    assert {"bearerAuth": []} in schema["security"]
    tags = {tag["name"] for tag in schema["tags"]}
    error = schema["components"]["schemas"]["Error"]
    assert "HTTPValidationError" not in schema["components"]["schemas"]
    by_id = {
        operation["operationId"]: operation
        for item in schema["paths"].values()
        for operation in item.values()
    }
    for op in OPERATIONS:
        documented = by_id[op.name]
        assert documented["summary"] and documented["description"], op.name
        assert len(op.description) <= 250, (op.name, len(op.description))
        assert set(documented["tags"]) <= tags, op.name
        assert documented["x-openings-access"] == op.access
        success = documented["responses"][str(op.status or 200)]
        assert success["content"]["application/json"]["schema"], op.name
        for status in ("401", "403", "422"):
            body = documented["responses"][status]["content"]["application/json"]["schema"]
            assert body == {"$ref": "#/components/schemas/Error"}, (op.name, status)
        if op.access != "read":
            assert "409" in documented["responses"], op.name
        if op.access == "owner":
            assert "Owner only" in documented["description"]
    assert {"code", "status", "message", "details"} <= set(
        schema["components"]["schemas"]["ErrorBody"]["properties"]
    )
    assert "conflict" in error["description"] and "transfer_used" in error["description"]
    # A create whose body names a parent documents its 404, as does a transport route.
    for operation_id in ("documents_create", "highlights_create", "notes_create", "files_upload"):
        assert "404" in by_id[operation_id]["responses"], operation_id
    skill_file = by_id["skills_file"]["responses"]["404"]["content"]["application/json"]
    assert skill_file["schema"] == {"$ref": "#/components/schemas/Error"}
    # Transport routes have readable operation ids too.
    assert {"auth_session", "transfers_upload", "transfers_download", "health"} <= set(by_id)
    assert not [
        name for name in by_id if name.endswith(("_get", "_post", "_put")) and "api_v1" in name
    ]


def test_a_documented_404_is_what_a_missing_parent_answers(client):
    missing = client.post(
        "/api/v1/career/highlights", json={"career_id": "missing", "text": "Synthetic."}
    )
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
    skill = client.get("/api/v1/skills/openings/files/references/missing.md")
    assert skill.status_code == 404 and skill.json()["error"]["code"] == "not_found"


def test_request_examples_are_valid_requests():
    for name, examples in EXAMPLES.items():
        (op,) = [op for op in OPERATIONS if op.name == name]
        body = next(
            parameter.annotation
            for parameter in inspect.signature(op.fn, eval_str=True).parameters.values()
            if isinstance(parameter.annotation, type)
            and issubclass(parameter.annotation, BaseModel)
        )
        for example in examples.values():
            body.model_validate(example["value"])
