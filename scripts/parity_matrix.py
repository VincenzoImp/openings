"""Generate the dashboard/REST/MCP parity matrix (docs/developer/parity.md).

The matrix joins four sources:

- the operation inventory (logical operations, REST routes, MCP tools);
- the running contract (OpenAPI inputs and MCP tool input schemas);
- the dashboard source (REST paths it really calls, raw-JSON editors);
- recorded browser evidence (REST calls the dashboard made during the e2e suite).

Usage, from the repository root:

    uv run python scripts/parity_matrix.py           # regenerate the matrix
    uv run python scripts/parity_matrix.py --check   # fail when it is out of date
    uv run python scripts/parity_matrix.py --e2e     # re-record browser evidence first

``--e2e`` needs the built dashboard and Playwright Chromium (see CONTRIBUTING).
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "backend/openings/operation-inventory.json"
FRONTEND = ROOT / "frontend"
SOURCES = FRONTEND / "src"
MATRIX = ROOT / "docs/developer/parity.md"
EVIDENCE = ROOT / "docs/developer/parity-e2e.json"
NOTES = ROOT / "docs/developer/parity-notes.json"
# The e2e helper marks its own setup requests with this header; they are not
# evidence of a dashboard path.
SETUP_HEADER = "x-openings-e2e-setup"
METHODS = ("GET", "POST", "PATCH", "PUT", "DELETE")
SUFFIX = re.compile(r"[^{}`]*\}((?:/(?:[\w-]+|\$\{[^}]*\}))+)")
LITERAL = re.compile(r"""(["'`])(/(?:\\.|(?!\1).)*)\1""", re.DOTALL)


def route_key(path):
    """A route path with anonymous parameters: /jobs/{job_id} -> /jobs/{}."""
    return re.sub(r"\{[^}]+\}", "{}", path).rstrip("/") or "/"


def contract():
    """OpenAPI document and MCP tool schemas of the application in this checkout."""
    sys.path.insert(0, str(ROOT / "backend"))
    from openings.app import create_app

    with tempfile.TemporaryDirectory(prefix="openings-parity-") as directory:
        app = create_app(Path(directory) / "workspace.sqlite", start_worker=False)
        tools = asyncio.run(app.state.mcp.list_tools())
        return app.openapi(), {tool.name: tool.input_schema for tool in tools}


def resolve(schema, components):
    """Follow references and optional wrappers down to one object schema."""
    seen = set()
    while schema:
        if "$ref" in schema:
            name = schema["$ref"].rsplit("/", 1)[-1]
            if name in seen:
                return {}
            seen.add(name)
            schema = components.get(name, {})
            continue
        options = [
            s for s in schema.get("anyOf", schema.get("oneOf", [])) if s.get("type") != "null"
        ]
        if len(options) == 1:
            schema = options[0]
            continue
        return schema
    return {}


def free_form(schema, components):
    """True for an object whose keys the contract does not define."""
    schema = resolve(schema, components)
    return schema.get("type") == "object" and not schema.get("properties")


def rest_inputs(openapi, method, path):
    """Input names of one route, its path parameters, and its free-form JSON inputs."""
    components = openapi.get("components", {}).get("schemas", {})
    operation = openapi["paths"].get(path, {}).get(method.lower())
    if operation is None:
        return set(), set(), set()
    parameters = operation.get("parameters", [])
    names = {parameter["name"] for parameter in parameters}
    in_path = {parameter["name"] for parameter in parameters if parameter["in"] == "path"}
    body = operation.get("requestBody", {}).get("content", {}).get("application/json", {})
    properties = resolve(body.get("schema", {}), components).get("properties", {})
    names.update(properties)
    loose = {name for name, schema in properties.items() if free_form(schema, components)}
    return names, in_path, loose


def mcp_inputs(schema):
    """Input names of one MCP tool, flattening a single wrapped model argument."""
    definitions = schema.get("$defs", {})
    names = set()
    for name, value in schema.get("properties", {}).items():
        inner = resolve(value, definitions)
        if "$ref" in value or any("$ref" in option for option in value.get("anyOf", [])):
            names.update(inner.get("properties", {}))
        else:
            names.add(name)
    return names


def dashboard_references(routes):
    """REST routes named by string literals in the dashboard source.

    A literal counts when it matches a route path; the HTTP method is the method
    literal in the same call, or GET. Combinations that are not real routes are
    dropped, so conditional paths and methods do not invent references.
    """
    references = defaultdict(set)
    for file in sorted(SOURCES.rglob("*.ts*")):
        text = file.read_text()
        for match in LITERAL.finditer(text):
            path = re.sub(r"\$\{[^}]*\}", "{}", match.group(2)).split("?")[0]
            if not path.startswith("/api/") and path != "/health":
                path = "/api/v1" + path
            # A literal chosen inside a template continues after the expression:
            # `${run ? "/collection/runs" : "/tasks"}/${id}` names /tasks/{} too.
            suffix = SUFFIX.match(text, match.end())
            keys = {route_key(path)}
            if suffix:
                keys.add(route_key(path + re.sub(r"\$\{[^}]*\}", "{}", suffix.group(1))))
            keys &= set(routes)
            if not keys:
                continue
            depth, index, limit = 0, match.end(), min(len(text), match.end() + 800)
            while index < limit:
                character = text[index]
                if character in "([{":
                    depth += 1
                elif character in ")]}":
                    if depth == 0:
                        break
                    depth -= 1
                index += 1
            methods = set(
                re.findall(r'"({})"'.format("|".join(METHODS)), text[match.end() : index])
            )
            for key in keys:
                for method in methods or {"GET"}:
                    if method in routes[key]:
                        references[(method, key)].add(file.relative_to(SOURCES).as_posix())
    return references


def source_mentions(files, name):
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    return any(pattern.search((SOURCES / file).read_text()) for file in files)


def raw_json_editor(files, name):
    pattern = re.compile(rf"""jsonValue\(\s*\w+,\s*["']{re.escape(name)}["']""")
    return any(pattern.search((SOURCES / file).read_text()) for file in files)


def record_e2e(routes):
    """Run the Chromium desktop e2e project with traces and keep dashboard requests."""
    with tempfile.TemporaryDirectory(prefix="openings-parity-e2e-") as directory:
        report = Path(directory) / "report.json"
        result = subprocess.run(
            [
                "npx",
                "playwright",
                "test",
                "--project=chromium",
                "--trace=on",
                "--reporter=json",
                "--output",
                str(Path(directory) / "results"),
            ],
            cwd=FRONTEND,
            env={**os.environ, "PLAYWRIGHT_JSON_OUTPUT_NAME": str(report)},
            stdout=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode:
            raise SystemExit("The e2e suite failed; evidence was not recorded.")
        evidence = defaultdict(set)

        def visit(suite):
            for child in suite.get("suites", []):
                visit(child)
            for spec in suite.get("specs", []):
                for test in spec["tests"]:
                    for attempt in test["results"]:
                        for attachment in attempt.get("attachments", []):
                            if attachment["name"] == "trace":
                                for route in trace_routes(Path(attachment["path"]), routes):
                                    evidence[route].add(spec["title"])

        visit(json.loads(report.read_text()))
    document = {
        "format": "openings-parity-e2e-v1",
        "project": "chromium",
        "routes": {
            f"{method} {path}": sorted(titles)
            for (method, path), titles in sorted(evidence.items())
        },
    }
    EVIDENCE.write_text(json.dumps(document, indent=2) + "\n")


def trace_routes(trace, routes):
    """REST requests the dashboard itself sent in one recorded test, unless refused."""
    found = set()
    with zipfile.ZipFile(trace) as archive:
        for name in archive.namelist():
            if not name.endswith(".network"):
                continue
            for line in archive.read(name).decode().splitlines():
                snapshot = json.loads(line).get("snapshot", {})
                request, response = snapshot.get("request", {}), snapshot.get("response", {})
                headers = {header["name"].lower() for header in request.get("headers", [])}
                # A request cut short by navigation has status -1. It still shows that
                # the dashboard sent it, and counting it keeps recordings repeatable.
                status = response.get("status", -1)
                if SETUP_HEADER in headers or not (status == -1 or 200 <= status < 400):
                    continue
                key = route_key(urlsplit(request["url"]).path)
                # Concrete identifiers are matched against the route templates.
                for template, methods in routes.items():
                    if request["method"] in methods and (
                        key == template
                        or re.fullmatch(re.escape(template).replace(r"\{\}", "[^/]+"), key)
                    ):
                        found.add((request["method"], template))
    return found


def cell(values):
    return "<br>".join(values) if values else "—"


def build():
    inventory = json.loads(INVENTORY.read_text())
    notes = json.loads(NOTES.read_text())
    evidence = json.loads(EVIDENCE.read_text())
    openapi, tools = contract()
    templates = {route_key(path): path for path in openapi["paths"]}
    routes = defaultdict(set)
    for entry in inventory["operations"] + inventory["exceptions"]:
        for route in entry["rest"]:
            routes[route_key(route["path"])].add(route["method"])
    references = dashboard_references(routes)
    exercised = {tuple(route.split(" ", 1)): titles for route, titles in evidence["routes"].items()}
    unknown_notes = set(notes["operations"]) - {entry["id"] for entry in inventory["operations"]}
    if unknown_notes:
        raise SystemExit(f"parity-notes.json names unknown operations: {sorted(unknown_notes)}")
    unknown_access = {
        entry["id"]
        for entry in inventory["operations"]
        if entry.get("access", "owner") not in inventory["access"]
    }
    if unknown_access:
        raise SystemExit(f"The inventory has unknown access levels: {sorted(unknown_access)}")

    rows = []
    for entry in inventory["operations"]:
        keys = [(route["method"], route_key(route["path"])) for route in entry["rest"]]
        files = sorted({file for key in keys for file in references.get(key, ())})
        tests = sorted({title for key in keys for title in exercised.get(key, ())})
        rest_names, in_path, free = set(), set(), set()
        for method, key in keys:
            names, parameters, loose = rest_inputs(openapi, method, templates.get(key, key))
            rest_names |= names
            in_path |= parameters
            free |= loose
        # The tool's own inputs; the names after it are deprecated aliases (#167).
        mcp_names = mcp_inputs(tools[entry["mcp"][0]]) if entry["mcp"] else set()
        rows.append(
            {
                "entry": entry,
                "files": files,
                "tests": tests,
                "direct": bool(files or tests),
                "raw": sorted(name for name in free if raw_json_editor(files, name)),
                "unmentioned": sorted(
                    name
                    for name in rest_names - in_path
                    if files and not source_mentions(files, name)
                ),
                "rest_only": sorted(rest_names - mcp_names) if entry["mcp"] else [],
                "mcp_only": sorted(mcp_names - rest_names) if entry["rest"] else [],
                "via": notes["operations"].get(entry["id"], {}).get("via", []),
                "note": notes["operations"].get(entry["id"], {}).get("note", ""),
            }
        )
    direct = {row["entry"]["id"] for row in rows if row["direct"]}
    for row in rows:
        missing = set(row["via"]) - direct
        if missing or (row["via"] and row["direct"]):
            raise SystemExit(f"parity-notes.json: check 'via' of {row['entry']['id']}")
        row["reachable"] = row["direct"] or bool(row["via"])

    out = [
        "# Parity matrix",
        "",
        "Generated by `scripts/parity_matrix.py`; do not edit by hand. Run",
        "`uv run python scripts/parity_matrix.py` after changing the operation inventory,",
        "a REST route, an MCP tool or the dashboard, and add `--e2e` after changing the",
        "browser tests. Remarks come from `parity-notes.json`.",
        "",
        "Design rule: every capability is manageable from the dashboard, REST and MCP",
        "alike. This page shows where that holds in the current code and lists every gap.",
        "",
        "How to read the evidence:",
        "",
        "- **Dashboard code** lists the dashboard source files that name the operation's",
        "  REST route. **E2E** counts the browser tests in which the dashboard itself",
        "  called the route without an error response (Chromium desktop; setup calls made",
        "  by the test helper are excluded). An operation with neither has no working",
        "  dashboard path.",
        "- **Editor** is `raw JSON` when a free-form JSON input is edited as JSON text.",
        "- **MCP** names the tool; the inventory also lists its deprecated aliases, which",
        "  are removed in 0.23.",
        "- Input comparisons use names from OpenAPI and the MCP tool schemas. A name the",
        "  dashboard files never mention cannot be set there; a mentioned name may still",
        "  lack a control, so those lists are lower bounds.",
        "- **Access** is `owner` for an operation that needs owner authority (the",
        "  dashboard session or an API token of kind `owner`) and refuses an API token",
        "  of kind `agent` with `403 forbidden`; `any` accepts both kinds.",
        "",
        "## Summary",
        "",
    ]
    total = len(rows)
    unreachable = [row for row in rows if not row["reachable"]]
    indirect = [row for row in rows if row["via"]]
    untested = [row for row in rows if row["direct"] and not row["tests"]]
    raw = [row for row in rows if row["raw"]]
    unmentioned = [row for row in rows if row["unmentioned"]]
    different = [row for row in rows if row["rest_only"] or row["mcp_only"]]
    one_sided = [row for row in rows if not row["entry"]["rest"] or not row["entry"]["mcp"]]
    owner_only = [row for row in rows if row["entry"].get("access") == "owner"]
    out += [
        "| Measure | Operations |",
        "|---|---|",
        f"| Logical operations in the inventory | {total} |",
        f"| Without REST or without MCP | {len(one_sided)} |",
        f"| Owner only (refused for an agent token) | {len(owner_only)} |",
        f"| Without a working dashboard path | {len(unreachable)} |",
        f"| Reached only through another operation | {len(indirect)} |",
        f"| With inputs the dashboard never mentions | {len(unmentioned)} |",
        f"| With free-form JSON edited as raw JSON | {len(raw)} |",
        f"| With different REST and MCP input names | {len(different)} |",
        f"| With a dashboard path exercised by e2e | {sum(bool(row['tests']) for row in rows)} |",
        f"| With a dashboard path but no e2e evidence | {len(untested)} |",
        "",
        "## Gaps",
        "",
        "### Operations without a working dashboard path",
        "",
        "The inventory names a dashboard location for each of these, but no dashboard",
        "code calls the route and no browser test reached it.",
        "",
        "| Operation | REST | MCP | Inventory says | Remark |",
        "|---|---|---|---|---|",
    ]

    def rest_cell(entry):
        return cell(
            [
                f"`{route['method']} {route['path'].removeprefix('/api/v1')}`"
                for route in entry["rest"]
            ]
        )

    def mcp_cell(entry):
        return cell([f"`{tool}`" for tool in entry["mcp"][:1]])

    for row in unreachable:
        entry = row["entry"]
        out.append(
            f"| `{entry['id']}` | {rest_cell(entry)} | {mcp_cell(entry)} | {entry['dashboard']} | {row['note'] or '—'} |"
        )
    out += [
        "",
        "### Operations reached only through another operation",
        "",
        "The dashboard offers the capability, but calls a different operation for it.",
        "The route itself is never called from the dashboard.",
        "",
        "| Operation | Dashboard uses | Remark |",
        "|---|---|---|",
    ]
    for row in indirect:
        via = ", ".join(f"`{name}`" for name in row["via"])
        out.append(f"| `{row['entry']['id']}` | {via} | {row['note'] or '—'} |")
    out += [
        "",
        "### Inputs the dashboard never mentions",
        "",
        "REST inputs whose names do not occur in the dashboard files that call the",
        "operation. They can be set over REST or MCP only.",
        "",
        "| Operation | Inputs | Remark |",
        "|---|---|---|",
    ]
    for row in unmentioned:
        names = ", ".join(f"`{name}`" for name in row["unmentioned"])
        out.append(f"| `{row['entry']['id']}` | {names} | {row['note'] or '—'} |")
    out += [
        "",
        "### Free-form JSON edited as raw JSON",
        "",
        "Structured data the owner can change only by editing JSON text.",
        "",
        "| Operation | Fields | Dashboard code | Remark |",
        "|---|---|---|---|",
    ]
    for row in raw:
        names = ", ".join(f"`{name}`" for name in row["raw"])
        out.append(
            f"| `{row['entry']['id']}` | {names} | {cell(row['files'])} | {row['note'] or '—'} |"
        )
    out += [
        "",
        "### REST and MCP input differences",
        "",
        "Input names present on one interface only. Path parameters, transport details",
        "and renamed arguments appear here; each needs a decision: align or document.",
        "",
        "| Operation | REST only | MCP only |",
        "|---|---|---|",
    ]
    for row in different:
        out.append(
            "| `{}` | {} | {} |".format(
                row["entry"]["id"],
                ", ".join(f"`{name}`" for name in row["rest_only"]) or "—",
                ", ".join(f"`{name}`" for name in row["mcp_only"]) or "—",
            )
        )
    out += [
        "",
        "### Owner-only operations",
        "",
        "Operations that need owner authority. An API token of kind `agent` is refused",
        "with `403 forbidden` on REST and MCP; `test_interfaces.py` checks each one.",
        "",
        "| Operation | REST | MCP | Remark |",
        "|---|---|---|---|",
    ]
    for row in owner_only:
        entry = row["entry"]
        out.append(
            f"| `{entry['id']}` | {rest_cell(entry)} | {mcp_cell(entry)} | {entry.get('notes') or '—'} |"
        )
    out += [
        "",
        "### Dashboard actions outside the logical operations",
        "",
        "REST routes the dashboard calls that the inventory records as transport",
        "exceptions, with the documented reason. Any other dashboard call maps to an",
        "operation above, and `test_interfaces.py` fails for a REST route or MCP tool",
        "missing from the inventory.",
        "",
        "| Exception | Dashboard code | MCP | Reason |",
        "|---|---|---|---|",
    ]
    for entry in inventory["exceptions"]:
        keys = [(route["method"], route_key(route["path"])) for route in entry["rest"]]
        files = sorted({file for key in keys for file in references.get(key, ())})
        if files:
            out.append(
                f"| `{entry['id']}` | {cell(files)} | {mcp_cell(entry)} | {entry['reason']} |"
            )
    out += [
        "",
        "### Dashboard paths without e2e evidence",
        "",
        cell([f"`{row['entry']['id']}`" for row in untested]).replace("<br>", ", "),
        "",
        "## Matrix",
    ]
    groups = defaultdict(list)
    for row in rows:
        groups[row["entry"]["group"]].append(row)
    for group, members in groups.items():
        out += [
            "",
            f"### {group}",
            "",
            "| Operation | REST | MCP | Access | Dashboard location | Dashboard code | Editor | E2E |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for row in members:
            entry = row["entry"]
            editor = "—"
            if row["direct"]:
                editor = "raw JSON: " + ", ".join(row["raw"]) if row["raw"] else "structured"
            code = cell(row["files"]) if row["direct"] else "**none**"
            if row["via"]:
                code = "via " + ", ".join(f"`{name}`" for name in row["via"])
            out.append(
                "| `{}`<br>{} | {} | {} | {} | {} | {} | {} | {} |".format(
                    entry["id"],
                    entry["operation"],
                    rest_cell(entry),
                    mcp_cell(entry),
                    entry.get("access", "any"),
                    entry["dashboard"],
                    code,
                    editor,
                    len(row["tests"]) or ("**0**" if row["direct"] else "—"),
                )
            )
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when parity.md is out of date")
    parser.add_argument("--e2e", action="store_true", help="re-record browser evidence first")
    arguments = parser.parse_args()
    if arguments.e2e:
        inventory = json.loads(INVENTORY.read_text())
        routes = defaultdict(set)
        for entry in inventory["operations"] + inventory["exceptions"]:
            for route in entry["rest"]:
                routes[route_key(route["path"])].add(route["method"])
        record_e2e(routes)
    matrix = build()
    if arguments.check:
        if MATRIX.read_text() != matrix:
            raise SystemExit(
                "docs/developer/parity.md is out of date; run scripts/parity_matrix.py."
            )
        return
    MATRIX.write_text(matrix)


if __name__ == "__main__":
    main()
