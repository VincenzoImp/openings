import argparse
import ipaddress
import logging
import os
import secrets
import tempfile
from pathlib import Path

import uvicorn

from .app import create_app
from .demo import seed_demo
from .errors import DomainError


def trusted_proxies(value):
    """Parse comma-separated proxy IPs/CIDRs; an empty value trusts no proxy."""
    entries = []
    for entry in (item.strip() for item in (value or "").split(",")):
        if not entry:
            continue
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            raise SystemExit(
                f"OPENINGS_TRUSTED_PROXIES must list IP addresses or CIDR ranges, not {entry!r}."
            ) from None
        entries.append(str(network) if "/" in entry else str(network.network_address))
    return entries


def proxy_options(value):
    """Uvicorn settings that accept forwarded client addresses only from trusted proxies."""
    entries = trusted_proxies(value)
    if not entries:
        return {"proxy_headers": False, "forwarded_allow_ips": ""}
    return {"proxy_headers": True, "forwarded_allow_ips": ",".join(entries)}


def demo_app(directory, port):
    """A demo workspace in ``directory``, never in $OPENINGS_DATABASE: the app and its notice.

    The workspace gets an owner password nobody knows: the printed link signs in once.
    """
    app = create_app(Path(directory) / "demo.sqlite", start_worker=False, demo=True)
    auth = app.state.auth
    if not auth.configured():
        auth.setup(secrets.token_urlsafe(32))
    token = seed_demo(app)["token"]
    origin = os.environ.get("OPENINGS_PUBLIC_URL", "").rstrip("/") or f"http://127.0.0.1:{port}"
    lines = (
        "",
        "Openings demo: a fictional workspace in a temporary file, deleted when this stops.",
        "No job site is contacted.",
        "",
        "Sign in (the link works once):",
        f"  {origin}/api/v1/auth/demo?ticket={auth.sign_in_link()}",
        "",
        'Connect an agent with the token "Claude Code":',
        f"  export OPENINGS_TOKEN={token}",
        (
            f"  claude mcp add --transport http openings {origin}/mcp/ "
            "--header 'Authorization: Bearer ${OPENINGS_TOKEN}'"
        ),
        f"  codex mcp add openings --url {origin}/mcp/ --bearer-token-env-var OPENINGS_TOKEN",
        "",
        f"Mapped another port? Replace {port}.",
        "",
    )
    return app, "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Run the Openings workspace.")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["demo"],
        help="demo: a disposable workspace of fictional data that contacts no job site",
    )
    parser.add_argument("--host", default=os.environ.get("OPENINGS_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("OPENINGS_PORT", "8080")))
    parser.add_argument(
        "--database", default=os.environ.get("OPENINGS_DATABASE", "data/openings.sqlite")
    )
    parser.add_argument(
        "--trusted-proxies",
        default=os.environ.get("OPENINGS_TRUSTED_PROXIES", ""),
        help="Comma-separated reverse-proxy IPs/CIDRs whose X-Forwarded-For/-Proto are trusted.",
    )
    args = parser.parse_args()
    options = proxy_options(args.trusted_proxies)
    # Openings' own messages (pre-upgrade copies, backups, compaction) beside uvicorn's.
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    logger = logging.getLogger("openings")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if args.command == "demo":
        # A temporary directory ($TMPDIR), removed when the server stops.
        with tempfile.TemporaryDirectory(prefix="openings-demo-") as directory:
            app, notice = demo_app(directory, args.port)
            print(notice, flush=True)
            uvicorn.run(app, host=args.host, port=args.port, log_level="info", **options)
        return
    try:
        app = create_app(args.database)
    except DomainError as error:
        # A workspace that cannot be opened safely (format, room for the pre-upgrade copy).
        raise SystemExit(f"Openings did not start: {error.message}") from None
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
        **options,
    )


if __name__ == "__main__":
    main()
