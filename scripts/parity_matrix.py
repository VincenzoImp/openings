"""Generate and enforce the dashboard/REST/MCP parity matrix (docs/developer/parity.md).

The matrix joins four sources:

- the operation inventory (logical operations, REST routes, MCP tools);
- the running contract (OpenAPI inputs and MCP tool input schemas);
- the dashboard source (REST paths it really calls, raw-JSON editors);
- recorded browser evidence (REST calls the dashboard made during the e2e suite).

Every difference between the three interfaces is a gap unless
docs/developer/parity-notes.json documents it with a reason (an exemption). The
rule, enforced by ``--check`` in pytest and by ``--gate`` after the browser
tests in CI: no operation lacks REST or MCP, every operation has a dashboard
path that a browser test exercised (or a documented exemption), and the
dashboard calls no REST route outside the inventory.

Usage, from the repository root:

    uv run python scripts/parity_matrix.py              # regenerate the matrix
    uv run python scripts/parity_matrix.py --check      # fail when stale or on a gap
    uv run python scripts/parity_matrix.py --e2e        # re-record browser evidence first
    uv run python scripts/parity_matrix.py --gate DIR   # check a fresh e2e recording

``--e2e`` needs the built dashboard and Playwright Chromium (see CONTRIBUTING).
``--gate DIR`` reads what the browser tests recorded in DIR when they ran with
``OPENINGS_PARITY_EVIDENCE=DIR`` (frontend/tests/fixtures.ts).
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "backend/openings/operation-inventory.json"
FRONTEND = ROOT / "frontend"
SOURCES = FRONTEND / "src"
MATRIX = ROOT / "docs/developer/parity.md"
EVIDENCE = ROOT / "docs/developer/parity-e2e.json"
NOTES = ROOT / "docs/developer/parity-notes.json"
# The browser tests write what the dashboard requested into this directory
# (frontend/tests/fixtures.ts); requests the e2e helpers make for their own
# setup carry a header and are left out there.
EVIDENCE_ENV = "OPENINGS_PARITY_EVIDENCE"
EVIDENCE_PROJECT = "chromium"
API = "/api/v1"
METHODS = ("GET", "POST", "PATCH", "PUT", "DELETE")
# Route templates whose last parameter is a path of several segments.
PATHS = set()
SUFFIX = re.compile(r"[^{}`]*\}((?:/(?:[\w-]+|\$\{[^}]*\}))+)")
LITERAL = re.compile(r"""(["'`])(/(?:\\.|(?!\1).)*)\1""", re.DOTALL)
IMPORT = re.compile(r"""from\s+["'](\.{1,2}/[^"']+)["']""")
# Files whose words count for the inputs of the routes a page calls: the page's
# own modules and the shared library, not the design system or the shell.
OWN_CODE = ("pages/", "library/")


def route_key(path):
    """A route path with anonymous parameters: /jobs/{job_id} -> /jobs/{}."""
    return re.sub(r"\{[^}]+\}", "{}", path).rstrip("/") or "/"


def inventory_routes(inventory):
    """Every REST route of the inventory, operations and exceptions: key -> methods."""
    routes = defaultdict(set)
    for entry in inventory["operations"] + inventory["exceptions"]:
        for route in entry["rest"]:
            routes[route_key(route["path"])].add(route["method"])
            # A last parameter named path takes several segments (a skill's file).
            if route["path"].endswith("/{path}"):
                PATHS.add(route_key(route["path"]))
    return routes


def template_of(key, routes, method=None):
    """The route template a concrete path key belongs to, or None."""
    if key in routes and (method is None or method in routes[key]):
        return key
    candidates = [
        template for template, methods in routes.items() if method is None or method in methods
    ]
    for template in candidates:
        if re.fullmatch(re.escape(template).replace(r"\{\}", "[^/]+"), key):
            return template
    for template in candidates:
        if template in PATHS:
            prefix = re.escape(template.removesuffix("{}")).replace(r"\{\}", "[^/]+")
            if re.fullmatch(prefix + ".+", key):
                return template
    return None


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


def api_literals():
    """String literals of the dashboard source that name a REST path: (file, path, text, end)."""
    for file in sorted(SOURCES.rglob("*.ts*")):
        text = file.read_text()
        for match in LITERAL.finditer(text):
            path = re.sub(r"\$\{[^}]*\}", "{}", match.group(2)).split("?")[0]
            if not path.startswith("/api/") and path != "/health":
                path = API + path
            yield file, path, text, match.end()


def dashboard_references(routes):
    """REST routes named by string literals in the dashboard source.

    A literal counts when it matches a route path; the HTTP method is the method
    literal in the same call, or GET. Combinations that are not real routes are
    dropped, so conditional paths and methods do not invent references.
    """
    references = defaultdict(set)
    for file, path, text, end in api_literals():
        # A literal chosen inside a template continues after the expression:
        # `${run ? "/collection/runs" : "/tasks"}/${id}` names /tasks/{} too.
        suffix = SUFFIX.match(text, end)
        keys = {route_key(path)}
        if suffix:
            keys.add(route_key(path + re.sub(r"\$\{[^}]*\}", "{}", suffix.group(1))))
        keys &= set(routes)
        if not keys:
            continue
        depth, index, limit = 0, end, min(len(text), end + 800)
        while index < limit:
            character = text[index]
            if character in "([{":
                depth += 1
            elif character in ")]}":
                if depth == 0:
                    break
                depth -= 1
            index += 1
        methods = set(re.findall(r'"({})"'.format("|".join(METHODS)), text[end:index]))
        for key in keys:
            for method in methods or {"GET"}:
                if method in routes[key]:
                    references[(method, key)].add(file.relative_to(SOURCES).as_posix())
    return references


def unknown_literals(routes):
    """Dashboard literals naming an /api/v1 path that no inventory route matches."""
    found = []
    for file, path, _, _ in api_literals():
        key = route_key(path)
        if not key.startswith(API + "/"):
            continue
        if template_of(key, routes) is None:
            found.append(f"{file.relative_to(SOURCES).as_posix()}: {path}")
    return sorted(set(found))


def imports_of(file):
    """Relative modules one dashboard file imports, as paths under SOURCES."""
    found = set()
    for target in IMPORT.findall((SOURCES / file).read_text()):
        base = (SOURCES / file).parent / target
        for candidate in (base.with_name(base.name + ".tsx"), base.with_name(base.name + ".ts")):
            if candidate.is_file():
                found.add(candidate.resolve().relative_to(SOURCES.resolve()).as_posix())
    return found


def own_code(files):
    """The files and the page and library modules they import, transitively."""
    seen, queue = set(files), list(files)
    while queue:
        for name in imports_of(queue.pop()):
            if name not in seen and name.startswith(OWN_CODE):
                seen.add(name)
                queue.append(name)
    return sorted(seen)


def source_mentions(files, name):
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    return any(pattern.search((SOURCES / file).read_text()) for file in files)


def raw_json_editor(files, name):
    pattern = re.compile(rf"""jsonValue\(\s*\w+,\s*["']{re.escape(name)}["']""")
    return any(pattern.search((SOURCES / file).read_text()) for file in files)


def recorded_requests(directory):
    """What the browser tests recorded, per request: test title, method, path,
    status, and whether the test gave the answer itself."""
    for file in sorted(Path(directory).glob("*.json")):
        record = json.loads(file.read_text())
        for request in record["requests"]:
            yield (
                record["title"],
                request["method"],
                request["path"],
                request["status"],
                request.get("answered", False),
            )


def evidence_document(directory, routes):
    """Exercised routes and unknown /api/v1 requests from one recorded e2e run.

    Routes the server answered are in ``routes``; routes a test answered itself
    (page.route) are in ``answered``, which counts only for an operation whose
    notes say why (``answered_by_test``).
    """
    evidence, answered, unknown = defaultdict(set), defaultdict(set), defaultdict(set)
    for title, method, path, status, by_test in recorded_requests(directory):
        key = route_key(path)
        template = template_of(key, routes, method)
        if template is None:
            if key.startswith(API + "/"):
                unknown[f"{method} {key}"].add(title)
            continue
        # A request cut short by navigation has status -1. It still shows that
        # the dashboard sent it, and counting it keeps recordings repeatable.
        if status == -1 or 200 <= status < 400:
            (answered if by_test else evidence)[(method, template)].add(title)

    def listed(found):
        return {
            f"{method} {path}": sorted(titles) for (method, path), titles in sorted(found.items())
        }

    return {
        "format": "openings-parity-e2e-v2",
        "project": EVIDENCE_PROJECT,
        "routes": listed(evidence),
        "answered": listed(answered),
        "unknown": {route: sorted(titles) for route, titles in sorted(unknown.items())},
    }


def record_e2e(routes):
    """Run the Chromium desktop e2e project and keep the requests the dashboard made."""
    with tempfile.TemporaryDirectory(prefix="openings-parity-e2e-") as directory:
        result = subprocess.run(
            [
                "npx",
                "playwright",
                "test",
                f"--project={EVIDENCE_PROJECT}",
                "--reporter=dot",
                "--output",
                str(Path(directory) / "results"),
            ],
            cwd=FRONTEND,
            env={**os.environ, EVIDENCE_ENV: str(Path(directory) / "evidence")},
            stdout=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode:
            raise SystemExit("The e2e suite failed; evidence was not recorded.")
        document = evidence_document(Path(directory) / "evidence", routes)
    EVIDENCE.write_text(json.dumps(document, indent=2) + "\n")


def cell(values):
    return "<br>".join(values) if values else "—"


def reasons(mapping, where):
    """A map of names to reasons from parity-notes.json; every reason is required."""
    for name, reason in mapping.items():
        if not isinstance(reason, str) or not reason.strip():
            raise SystemExit(f"parity-notes.json: {where} '{name}' needs a reason")
    return mapping


def analyse(evidence):
    """Rows of the matrix, the gaps and the documented exemptions, for one evidence document."""
    inventory = json.loads(INVENTORY.read_text())
    notes = json.loads(NOTES.read_text())
    openapi, tools = contract()
    templates = {route_key(path): path for path in openapi["paths"]}
    routes = inventory_routes(inventory)
    references = dashboard_references(routes)
    exercised = {tuple(route.split(" ", 1)): titles for route, titles in evidence["routes"].items()}
    by_tests = {
        tuple(route.split(" ", 1)): titles for route, titles in evidence.get("answered", {}).items()
    }
    known = {entry["id"] for entry in inventory["operations"]}
    unknown_notes = set(notes["operations"]) - known
    if unknown_notes:
        raise SystemExit(f"parity-notes.json names unknown operations: {sorted(unknown_notes)}")
    unknown_access = {
        entry["id"]
        for entry in inventory["operations"]
        if entry.get("access", "owner") not in inventory["access"]
    }
    if unknown_access:
        raise SystemExit(f"The inventory has unknown access levels: {sorted(unknown_access)}")
    shared_inputs = reasons(notes.get("inputs", {}), "input")
    stale = []

    rows = []
    for entry in inventory["operations"]:
        note = notes["operations"].get(entry["id"], {})
        reasons(
            {key: note[key] for key in ("exempt", "note", "answered_by_test") if key in note},
            f"remark of {entry['id']}:",
        )
        keys = [(route["method"], route_key(route["path"])) for route in entry["rest"]]
        files = sorted({file for key in keys for file in references.get(key, ())})
        tests = {title for key in keys for title in exercised.get(key, ())}
        if note.get("answered_by_test"):
            tests |= {title for key in keys for title in by_tests.get(key, ())}
        tests = sorted(tests)
        rest_names, in_path, free = set(), set(), set()
        for method, key in keys:
            names, parameters, loose = rest_inputs(openapi, method, templates.get(key, key))
            rest_names |= names
            in_path |= parameters
            free |= loose
        # A tool the app does not register fails test_interfaces.py instead.
        mcp_names = mcp_inputs(tools.get(entry["mcp"][0], {})) if entry["mcp"] else set()
        code = own_code(files)
        unmentioned = sorted(
            name for name in rest_names - in_path if files and not source_mentions(code, name)
        )
        input_reasons = reasons(note.get("inputs", {}), f"input of {entry['id']}")
        interface_reasons = reasons(note.get("interfaces", {}), f"interface input of {entry['id']}")
        rest_only = sorted(rest_names - mcp_names) if entry["mcp"] else []
        mcp_only = sorted(mcp_names - rest_names) if entry["rest"] else []
        stale += [
            f"{entry['id']}: input '{name}' has a control or no longer exists"
            for name in sorted(set(input_reasons) - set(unmentioned))
        ]
        stale += [
            f"{entry['id']}: interface input '{name}' is on both interfaces or gone"
            for name in sorted(set(interface_reasons) - set(rest_only) - set(mcp_only))
        ]
        rows.append(
            {
                "entry": entry,
                "files": files,
                "tests": tests,
                "direct": bool(files or tests),
                "raw": sorted(name for name in free if raw_json_editor(code, name)),
                "unmentioned": unmentioned,
                "input_reasons": {
                    name: input_reasons.get(name) or shared_inputs.get(name) for name in unmentioned
                },
                "rest_only": rest_only,
                "mcp_only": mcp_only,
                "interface_reasons": interface_reasons,
                "via": note.get("via", []),
                "exempt": note.get("exempt", ""),
                "answered": note.get("answered_by_test", ""),
                "note": note.get("note", ""),
            }
        )
    by_id = {row["entry"]["id"]: row for row in rows}
    for row in rows:
        identifier = row["entry"]["id"]
        if any(name not in by_id for name in row["via"]):
            raise SystemExit(f"parity-notes.json: 'via' of {identifier} names an unknown operation")
        if row["via"] and not row["note"]:
            raise SystemExit(
                f"parity-notes.json: {identifier} is reached via another operation; say why in 'note'"
            )
        if row["direct"] and (row["via"] or row["exempt"]):
            stale.append(f"{identifier}: has its own dashboard path; remove 'via' or 'exempt'")
        if row["via"] and row["exempt"]:
            stale.append(f"{identifier}: 'via' and 'exempt' exclude each other")
        if row["answered"] and not row["tests"]:
            stale.append(f"{identifier}: 'answered_by_test' but no browser test calls it")
    if stale:
        raise SystemExit("parity-notes.json has stale exemptions:\n- " + "\n- ".join(stale))

    gaps = defaultdict(list)
    for row in rows:
        entry, identifier = row["entry"], row["entry"]["id"]
        if not entry["rest"] or not entry["mcp"]:
            gaps["one_sided"].append(identifier)
        if not row["direct"] and not row["via"] and not row["exempt"]:
            gaps["no_dashboard"].append(identifier)
        if row["direct"] and not row["tests"]:
            gaps["no_e2e"].append(identifier)
        untested = [name for name in row["via"] if not by_id[name]["tests"]]
        if untested:
            gaps["via_without_e2e"].append(f"{identifier} (via {', '.join(untested)})")
        missing = [name for name, reason in row["input_reasons"].items() if not reason]
        if missing:
            gaps["inputs"].append(f"{identifier}: {', '.join(missing)}")
        differing = [
            name
            for name in row["rest_only"] + row["mcp_only"]
            if name not in row["interface_reasons"]
        ]
        if differing:
            gaps["interfaces"].append(f"{identifier}: {', '.join(differing)}")
        if row["raw"]:
            gaps["raw_json"].append(f"{identifier}: {', '.join(row['raw'])}")
    for path in unknown_literals(routes):
        gaps["unknown_routes"].append(f"dashboard source {path}")
    for route, titles in evidence.get("unknown", {}).items():
        gaps["unknown_routes"].append(f"called in e2e: {route} ({titles[0]})")
    return inventory, rows, gaps, references


GAP_TITLES = {
    "one_sided": "Operations without REST or without MCP",
    "no_dashboard": "Operations without a dashboard path and without an exemption",
    "no_e2e": "Dashboard paths no browser test exercised",
    "via_without_e2e": "Operations reached through an operation no browser test exercised",
    "inputs": "Inputs without a dashboard control and without a reason",
    "interfaces": "Inputs on one interface only, without a reason",
    "raw_json": "Free-form JSON edited as raw JSON",
    "unknown_routes": "Dashboard requests outside the inventory",
}


def gap_lines(gaps):
    return [f"{GAP_TITLES[kind]}: {item}" for kind in GAP_TITLES for item in gaps.get(kind, [])]


def build(inventory, rows, gaps, references):
    out = [
        "# Parity matrix",
        "",
        "Generated by `scripts/parity_matrix.py`; do not edit by hand. Run",
        "`uv run python scripts/parity_matrix.py` after changing the operation inventory,",
        "a REST route, an MCP tool or the dashboard, and add `--e2e` after changing the",
        "browser tests. Exemptions and remarks come from `parity-notes.json`.",
        "",
        "Design rule: every capability is manageable from the dashboard, REST and MCP",
        "alike. Every difference is a gap unless it is documented here with its reason;",
        "`pytest` and the browser tests in CI fail on a gap (see CONTRIBUTING, Parity).",
        "",
        "How to read the evidence:",
        "",
        "- **Dashboard code** lists the dashboard source files that name the operation's",
        "  REST route. **E2E** counts the browser tests in which the dashboard itself",
        "  called the route without an error response (Chromium desktop; setup calls made",
        "  by the test helpers are excluded).",
        "- **Editor** is `raw JSON` when a free-form JSON input is edited as JSON text.",
        "- **MCP** names the tool, `<resource>_<verb>`.",
        "- Input comparisons use names from OpenAPI and the MCP tool schemas. An input",
        "  counts as offered when its name occurs in the files that call the route or in",
        "  the page and library modules they import; a mentioned name may still lack a",
        "  control, so the lists of inputs without a control are lower bounds.",
        "- **Access** is `owner` for an operation that needs owner authority (the",
        "  dashboard session or an API token of kind `owner`) and refuses an API token",
        "  of kind `agent` with `403 forbidden`; `any` accepts both kinds.",
        "",
        "## Summary",
        "",
    ]
    total = len(rows)
    exempt = [row for row in rows if row["exempt"]]
    indirect = [row for row in rows if row["via"]]
    unmentioned = [row for row in rows if row["unmentioned"]]
    different = [row for row in rows if row["rest_only"] or row["mcp_only"]]
    owner_only = [row for row in rows if row["entry"].get("access") == "owner"]
    open_gaps = sum(len(items) for items in gaps.values())
    out += [
        "| Measure | Operations |",
        "|---|---|",
        f"| Logical operations in the inventory | {total} |",
        f"| With REST and MCP | {sum(bool(r['entry']['rest'] and r['entry']['mcp']) for r in rows)} |",
        f"| Owner only (refused for an agent token) | {len(owner_only)} |",
        f"| With a dashboard path exercised by e2e | {sum(bool(row['tests']) for row in rows)} |",
        f"| Reached through another operation (documented) | {len(indirect)} |",
        f"| Without a dashboard path: agent only (documented) | {len(exempt)} |",
        f"| With inputs only agents and scripts set (documented) | {len(unmentioned)} |",
        f"| With inputs on one interface only (documented) | {len(different)} |",
        f"| **Gaps** | **{open_gaps}** |",
        "",
        "## Gaps",
        "",
    ]
    if open_gaps:
        out += ["Each line is a gap: close it, or document it with a reason.", ""]
        out += [f"- {line}" for line in gap_lines(gaps)]
    else:
        out.append("None. Every difference below is documented with its reason.")

    def rest_cell(entry):
        return cell(
            [
                f"`{route['method']} {route['path'].removeprefix('/api/v1')}`"
                for route in entry["rest"]
            ]
        )

    def mcp_cell(entry):
        return cell([f"`{tool}`" for tool in entry["mcp"][:1]])

    out += [
        "",
        "## Documented exemptions",
        "",
        "### Operations without a dashboard path",
        "",
        "Operations only an API token performs. The dashboard shows what they did.",
        "",
        "| Operation | REST | MCP | Dashboard shows | Reason |",
        "|---|---|---|---|---|",
    ]
    for row in exempt:
        entry = row["entry"]
        out.append(
            f"| `{entry['id']}` | {rest_cell(entry)} | {mcp_cell(entry)} | {entry['dashboard']} | {row['exempt']} |"
        )
    out += [
        "",
        "### Operations reached through another operation",
        "",
        "The dashboard offers the capability through a different operation, which a",
        "browser test exercises; the route itself is not called from the dashboard.",
        "",
        "| Operation | Dashboard uses | Reason |",
        "|---|---|---|",
    ]
    for row in indirect:
        via = ", ".join(f"`{name}`" for name in row["via"])
        out.append(f"| `{row['entry']['id']}` | {via} | {row['note']} |")
    out += [
        "",
        "### Inputs only agents and scripts set",
        "",
        "REST inputs whose names do not occur in the dashboard code of the operation.",
        "",
        "| Operation | Input | Reason |",
        "|---|---|---|",
    ]
    for row in unmentioned:
        for name in row["unmentioned"]:
            reason = row["input_reasons"][name] or "**no reason: a gap**"
            out.append(f"| `{row['entry']['id']}` | `{name}` | {reason} |")
    out += [
        "",
        "### Inputs on one interface only",
        "",
        "Input names present on REST or MCP only.",
        "",
        "| Operation | Input | Interface | Reason |",
        "|---|---|---|---|",
    ]
    for row in different:
        for name, side in [(n, "REST") for n in row["rest_only"]] + [
            (n, "MCP") for n in row["mcp_only"]
        ]:
            reason = row["interface_reasons"].get(name) or "**no reason: a gap**"
            out.append(f"| `{row['entry']['id']}` | `{name}` | {side} | {reason} |")
    answered = [row for row in rows if row["answered"]]
    out += [
        "",
        "### Browser tests that answer for the server",
        "",
        "The dashboard sends the request and handles the answer; the test gives the",
        "answer the server gives, because the real one would disturb the other tests.",
        "",
        "| Operation | Reason |",
        "|---|---|",
    ]
    out += [f"| `{row['entry']['id']}` | {row['answered']} |" for row in answered]
    out += [
        "",
        "## Owner-only operations",
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
        "## Dashboard actions outside the logical operations",
        "",
        "REST routes the dashboard calls that the inventory records as transport",
        "exceptions, with the documented reason. Any other dashboard call maps to an",
        "operation, and `test_interfaces.py` fails for a REST route or MCP tool",
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
    out += ["", "## Matrix"]
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
            elif row["exempt"]:
                code = "agent only"
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


def fail_on(gaps, what):
    lines = gap_lines(gaps)
    if lines:
        raise SystemExit(
            f"Parity gaps ({what}). Close each one, or document it with a reason in "
            "docs/developer/parity-notes.json (see CONTRIBUTING, Parity):\n- " + "\n- ".join(lines)
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="fail when parity.md is stale or a gap is open"
    )
    parser.add_argument("--e2e", action="store_true", help="re-record browser evidence first")
    parser.add_argument(
        "--gate",
        metavar="DIR",
        help=f"check the requests the browser tests recorded in DIR ({EVIDENCE_ENV})",
    )
    arguments = parser.parse_args()
    inventory = json.loads(INVENTORY.read_text())
    if arguments.gate:
        directory = Path(arguments.gate)
        if not any(directory.glob("*.json")):
            raise SystemExit(
                f"No browser evidence in {directory}; run the e2e tests with {EVIDENCE_ENV}."
            )
        fresh = evidence_document(directory, inventory_routes(inventory))
        _, rows, gaps, _ = analyse(fresh)
        fail_on(gaps, "this browser test run")
        committed = json.loads(EVIDENCE.read_text())
        stale = set(fresh["routes"]) ^ set(committed["routes"])
        if stale:
            print(
                "Note: docs/developer/parity-e2e.json differs from this run for "
                + ", ".join(sorted(stale))
                + "; record it again with --e2e."
            )
        print(f"Parity: {len(rows)} operations, no gap in this browser test run.")
        return
    if arguments.e2e:
        record_e2e(inventory_routes(inventory))
    analysis = analyse(json.loads(EVIDENCE.read_text()))
    matrix = build(*analysis)
    if arguments.check:
        if MATRIX.read_text() != matrix:
            raise SystemExit(
                "docs/developer/parity.md is out of date; run scripts/parity_matrix.py."
            )
        fail_on(analysis[2], "the committed evidence")
        return
    MATRIX.write_text(matrix)
    gaps = gap_lines(analysis[2])
    if gaps:
        print(f"{len(gaps)} parity gaps; see docs/developer/parity.md.")


if __name__ == "__main__":
    main()
