#!/usr/bin/env python3
"""Copy the workflow skills served by your Openings server into .agents/skills/.

Usage: python3 .agents/scripts/fetch_skills.py

Agents connected over MCP can already read skills with skills_get, the prompts
or the openings://skills/<name> resources.
This copy serves clients that load Agent Skills from disk, and always matches
the server version. Needs OPENINGS_URL and OPENINGS_TOKEN (launch.py sets the
URL); OPENINGS_CA_FILE is used for a private certificate authority.
Skills fetched earlier but no longer served are removed; others are kept.
"""
from pathlib import Path, PurePosixPath
import json
import os
import shutil
import ssl
import urllib.parse
import urllib.request

root = Path(__file__).resolve().parents[2]
target = root / '.agents/skills'
manifest = target / '.fetched.json'
origin = os.environ.get('OPENINGS_URL', '').rstrip('/')
token = os.environ.get('OPENINGS_TOKEN', '')
if not origin or not token:
    raise SystemExit('Set OPENINGS_URL and OPENINGS_TOKEN (or run through launch.py).')
context = ssl.create_default_context()
if os.environ.get('OPENINGS_CA_FILE'):
    context.load_verify_locations(os.environ['OPENINGS_CA_FILE'])


def get(path):
    request = urllib.request.Request(origin + '/api/v1' + path,
                                     headers={'Authorization': f'Bearer {token}'})
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        return json.load(response)


version = get('/workspace').get('version', 'unknown')
skills = get('/skills')['items']
if not skills:
    raise SystemExit('The server lists no skills; nothing was changed.')
previous = json.loads(manifest.read_text())['skills'] if manifest.is_file() else []
for name in previous:
    if name not in {skill['name'] for skill in skills}:
        shutil.rmtree(target / name, ignore_errors=True)
for skill in skills:
    folder = target / skill['name']
    shutil.rmtree(folder, ignore_errors=True)
    for relative in skill['files']:
        path = PurePosixPath(relative)
        if path.is_absolute() or '..' in path.parts:
            raise SystemExit(f'Refusing unsafe path {relative!r} from the server.')
        quoted = urllib.parse.quote(relative)
        content = get(f"/skills/{urllib.parse.quote(skill['name'])}/files/{quoted}")['content']
        file = folder / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)
manifest.write_text(json.dumps({'origin': origin, 'version': version,
                                'skills': [s['name'] for s in skills]}, indent=2) + '\n')
print(f'Fetched {len(skills)} skills from Openings {version} into .agents/skills/')
