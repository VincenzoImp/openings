"""The layering of docs/developer/architecture.md, read from the source without importing it.

Services never import the interfaces, MCP or FastAPI routing; the core never starts a
model, browser or TeX runtime; only the provider gate builds HTTP clients.
"""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "openings"
# The hosts that bind services to REST and MCP.
INTERFACES = {"app.py", "mcp_server.py", "openapi.py", "__main__.py"}
# The modules of the provider gate (discovery/network.py: httpx with pinned addresses;
# collectors/pinning.py: the requests and curl sessions of the vendored JobSpy).
GATE = {"discovery/network.py", "collectors/pinning.py"}
HTTP_CLIENTS = {"httpx", "requests", "urllib3", "curl_cffi", "aiohttp", "http.client", "socket"}
RUNTIMES = {"subprocess", "multiprocessing", "anthropic", "openai", "transformers", "torch"}
RUNTIMES |= {"llama_cpp", "ollama", "playwright", "selenium", "pyppeteer"}
SPAWNS = {"system", "popen", "execv", "execvp", "execl", "spawnv", "spawnl", "startfile"}


def modules(vendored=False):
    for path in sorted(PACKAGE.rglob("*.py")):
        name = path.relative_to(PACKAGE).as_posix()
        if vendored or not name.startswith("_vendor/"):
            yield name, ast.parse(path.read_text(), name)


def imports(name, tree):
    """Every imported module as a dotted name, relative imports resolved to ``openings``."""
    package = ["openings", *name.split("/")[:-1]]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, None
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                base = ".".join(package[: len(package) - node.level + 1] + ([base] if base else []))
            for alias in node.names:
                yield base, alias.name


def within(module, roots):
    return any(module == root or module.startswith(root + ".") for root in roots)


def test_services_never_import_the_interfaces_or_routing():
    bound = {"openings.interfaces", "openings.app", "openings.mcp_server", "openings.openapi"}
    found = []
    for name, tree in modules():
        if name in INTERFACES or name.startswith("interfaces/"):
            continue
        for module, member in imports(name, tree):
            # A streamed upload or download takes the request and returns a response type.
            web_type = module == "fastapi.responses" or (module, member) == ("fastapi", "Request")
            names = (module, f"{module}.{member}")
            if any(within(item, {"mcp", *bound}) for item in names) or (
                within(module, {"fastapi"}) and not web_type
            ):
                found.append((name, module, member))
    assert found == []


def test_the_core_never_starts_a_model_browser_or_tex_runtime():
    found = []
    for name, tree in modules(vendored=True):
        found += [(name, module) for module, _ in imports(name, tree) if within(module, RUNTIMES)]
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr in SPAWNS
            ):
                found.append((name, "os." + node.attr))
    assert found == []


def test_only_the_provider_gate_builds_http_clients():
    found = [
        (name, module)
        for name, tree in modules()
        if name not in GATE
        for module, _ in imports(name, tree)
        if within(module, HTTP_CLIENTS)
    ]
    assert found == []
