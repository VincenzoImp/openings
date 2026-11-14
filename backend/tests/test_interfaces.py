"""Owner-only access: an agent token is refused on every owner operation, which is REST only."""

import re

from fastapi.testclient import TestClient

from openings.interfaces import OPERATIONS, TRANSPORT_ONLY

# One representative REST request per owner-only operation or transport route. An
# operation declared access=owner without an entry fails the test.
OWNER_ONLY_CALLS = {
    "owner_password_update": {"json": {"password": "another-synthetic-password"}},
    "tokens_list": {},
    "tokens_create": {"json": {"name": "Escalation"}},
    "tokens_revoke": {},
    "backups_list": {},
    "backups_delete": {},
    "POST /backup/restore": {"content": b"SQLite format 3\x00"},
    "GET /backups/{name}": {},
}


def test_owner_only_operations_refuse_an_agent_token(app, agent_token, owner_token):
    owner_ops = {op.name: op for op in OPERATIONS if op.access == "owner"}
    routes = {
        **{name: (op.method, op.path) for name, op in owner_ops.items()},
        **{
            f"{method} {path}": (method, path)
            for method, path, reason in TRANSPORT_ONLY
            if reason.startswith("Owner only")
        },
    }
    assert set(routes) == set(OWNER_ONLY_CALLS)
    with TestClient(app, base_url="http://localhost:8080") as client:
        capabilities = client.get("/api/v1/capabilities", headers=agent_token["headers"]).json()
        assert capabilities["token_kind"] == "agent"
        access = {item["name"]: item["access"] for item in capabilities["operations"]}
        assert {name for name, kind in access.items() if kind == "owner"} == set(owner_ops)
        owner_view = client.get("/api/v1/capabilities", headers=owner_token["headers"])
        assert owner_view.json()["token_kind"] == "owner"
        assert len(owner_view.content) < 12_000
        for name, (method, path) in routes.items():
            response = client.request(
                method,
                "/api/v1" + re.sub(r"\{[^}]+\}", "missing", path),
                headers=agent_token["headers"],
                **OWNER_ONLY_CALLS[name],
            )
            assert response.status_code == 403, (name, response.text)
            assert response.json()["error"]["code"] == "forbidden", name
        # The owner's token is not refused for want of authority.
        for name in ("tokens_list", "backups_list"):
            method, path = routes[name]
            assert client.request(
                method, "/api/v1" + path, headers=owner_token["headers"]
            ).is_success
