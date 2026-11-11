#!/usr/bin/env python3
"""Start any agent client from this checkout with Openings trust and token.

Usage: python3 .agents/scripts/launch.py <client> [args...]
Example: python3 .agents/scripts/launch.py codex

Sets OPENINGS_URL from .agents/mcp.json, points each runtime's CA variable at
OPENINGS_CA_FILE (or certs/openings-ca.pem when present) for a private CA, asks
for OPENINGS_TOKEN when the environment lacks it, and checks the token against
Openings before starting the client. A rejected token is asked for again, and
an owner token is accepted with a note that an agent token is enough.
The token stays in the client's process environment and is never written.
"""
from pathlib import Path
from urllib.parse import urlsplit
import getpass
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

root = Path(__file__).resolve().parents[2]
if len(sys.argv) < 2:
    raise SystemExit(__doc__.strip())

url = urlsplit(json.loads((root / '.agents/mcp.json').read_text())['mcpServers']['openings']['url'])
origin = f'{url.scheme}://{url.netloc}'
os.environ.setdefault('OPENINGS_URL', origin)
workspace = f'{origin}/api/v1/workspace'
context = ssl.create_default_context()
local_ca = root / 'certs/openings-ca.pem'
ca = os.environ.get('OPENINGS_CA_FILE') or (str(local_ca) if local_ca.is_file() else '')
if ca:
    os.environ['OPENINGS_CA_FILE'] = ca
    os.environ.setdefault('NODE_EXTRA_CA_CERTS', ca)    # Claude Code, Gemini CLI, Cursor, VS Code, opencode
    os.environ.setdefault('CODEX_CA_CERTIFICATE', ca)   # Codex
    context.load_verify_locations(ca)


def accepted(token):
    """Return True or False for the server's answer, None if it cannot be reached."""
    request = urllib.request.Request(workspace, headers={'Authorization': f'Bearer {token}'})
    try:
        with urllib.request.urlopen(request, timeout=10, context=context) as response:
            try:
                kind = json.load(response).get('actor', {}).get('token_kind')
            except ValueError:
                kind = None
            if kind == 'owner':
                print('This is an owner token with full access. An agent token '
                      '(Settings → Agent access) is enough for an agent.', file=sys.stderr)
            return True
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return False
        print(f'Openings check returned HTTP {error.code}; starting anyway.', file=sys.stderr)
    except OSError as error:
        print(f'Openings is unreachable ({error}); starting anyway.', file=sys.stderr)
    return None


token = os.environ.get('OPENINGS_TOKEN', '').strip()
while True:
    if not token:
        if not sys.stdin.isatty():
            raise SystemExit('OPENINGS_TOKEN is not set and there is no terminal to ask for it')
        token = getpass.getpass('Openings token: ').strip()
        continue
    if accepted(token) is not False:
        break
    print(f'Openings rejected the token ({len(token)} characters).', file=sys.stderr)
    if not sys.stdin.isatty():
        raise SystemExit('Set a valid OPENINGS_TOKEN and start again')
    token = ''

os.environ['OPENINGS_TOKEN'] = token
os.chdir(root)
os.execvp(sys.argv[1], sys.argv[1:])
