"""The parity gate (issue #136): an operation on one interface only, a dashboard
path no browser test used, or a dashboard request outside the inventory is a gap,
and only a documented reason exempts it. The committed matrix is checked by
test_interfaces.test_parity_matrix_is_current; CI runs the gate on the requests
of its own browser test run (scripts/parity_matrix.py --gate)."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def parity():
    spec = importlib.util.spec_from_file_location(
        "parity_matrix", ROOT / "scripts/parity_matrix.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # The contract of this checkout, read once for every test of the module.
    contract = module.contract()
    module.contract = lambda: contract
    return module


def with_operation(parity, tmp_path, monkeypatch, **fields):
    inventory = json.loads(parity.INVENTORY.read_text())
    inventory["operations"].append(
        {
            "id": "synthetic.one_sided",
            "group": "Archive",
            "operation": "A synthetic operation",
            "rest": [{"method": "GET", "path": "/api/v1/synthetic"}],
            "mcp": [],
            "dashboard": "Nowhere",
            **fields,
        }
    )
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(inventory))
    monkeypatch.setattr(parity, "INVENTORY", path)


def with_notes(parity, tmp_path, monkeypatch, change):
    notes = json.loads(parity.NOTES.read_text())
    change(notes)
    path = tmp_path / "notes.json"
    path.write_text(json.dumps(notes))
    monkeypatch.setattr(parity, "NOTES", path)


def committed(parity):
    return json.loads(parity.EVIDENCE.read_text())


def test_the_committed_evidence_has_no_gap(parity):
    _, rows, gaps, _ = parity.analyse(committed(parity))
    assert parity.gap_lines(gaps) == []
    assert all(row["tests"] or row["via"] or row["exempt"] for row in rows)


def test_an_operation_on_one_interface_without_a_dashboard_path_fails(
    parity, tmp_path, monkeypatch
):
    with_operation(parity, tmp_path, monkeypatch)
    _, _, gaps, _ = parity.analyse(committed(parity))
    assert gaps["one_sided"] == ["synthetic.one_sided"]
    assert gaps["no_dashboard"] == ["synthetic.one_sided"]
    with pytest.raises(SystemExit, match="Operations without REST or without MCP"):
        parity.fail_on(gaps, "a test")


def test_only_a_reason_exempts_an_operation_without_a_dashboard_path(parity, tmp_path, monkeypatch):
    with_operation(parity, tmp_path, monkeypatch, mcp=["synthetic_get"])
    with_notes(
        parity,
        tmp_path,
        monkeypatch,
        lambda notes: notes["operations"].update(
            {"synthetic.one_sided": {"exempt": "Only an agent token calls it."}}
        ),
    )
    _, _, gaps, _ = parity.analyse(committed(parity))
    assert parity.gap_lines(gaps) == []
    with_notes(
        parity,
        tmp_path,
        monkeypatch,
        lambda notes: notes["operations"].update({"synthetic.one_sided": {"exempt": " "}}),
    )
    with pytest.raises(SystemExit, match="exempt"):
        _, _, gaps, _ = parity.analyse(committed(parity))
        parity.fail_on(gaps, "a test")


def test_a_dashboard_path_needs_a_browser_test(parity):
    evidence = committed(parity)
    evidence["routes"] = {
        route: titles
        for route, titles in evidence["routes"].items()
        if route != "POST /api/v1/sources/preview"
    }
    _, _, gaps, _ = parity.analyse(evidence)
    assert gaps["no_e2e"] == ["sources.preview"]


def write_run(directory, requests):
    directory.mkdir()
    (directory / "one.json").write_text(
        json.dumps({"title": "a synthetic test", "file": "x.spec.ts", "requests": requests})
    )


def test_a_dashboard_request_outside_the_inventory_fails(parity, tmp_path):
    routes = parity.inventory_routes(json.loads(parity.INVENTORY.read_text()))
    write_run(
        tmp_path / "run",
        [
            {"method": "GET", "path": "/api/v1/jobs/abc", "status": 200},
            {"method": "GET", "path": "/api/v1/not-an-operation", "status": 404},
        ],
    )
    fresh = parity.evidence_document(tmp_path / "run", routes)
    assert fresh["routes"] == {"GET /api/v1/jobs/{}": ["a synthetic test"]}
    assert fresh["unknown"] == {"GET /api/v1/not-an-operation": ["a synthetic test"]}
    evidence = committed(parity)
    evidence["unknown"] = fresh["unknown"]
    _, _, gaps, _ = parity.analyse(evidence)
    assert gaps["unknown_routes"] == [
        "called in e2e: GET /api/v1/not-an-operation (a synthetic test)"
    ]


def test_an_answer_a_test_gives_counts_only_where_the_notes_say_why(parity, tmp_path):
    routes = parity.inventory_routes(json.loads(parity.INVENTORY.read_text()))
    write_run(
        tmp_path / "run",
        [
            {"method": "POST", "path": "/api/v1/auth/password", "status": 200, "answered": True},
            {"method": "POST", "path": "/api/v1/sources/preview", "status": 200, "answered": True},
        ],
    )
    fresh = parity.evidence_document(tmp_path / "run", routes)
    assert fresh["routes"] == {}
    _, rows, _, _ = parity.analyse(fresh)
    tested = {row["entry"]["id"]: row["tests"] for row in rows}
    assert tested["password.update"] == ["a synthetic test"]
    assert tested["sources.preview"] == []
