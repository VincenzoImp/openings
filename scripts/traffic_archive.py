"""Append one dated line of repository traffic to a private JSON Lines file.

GitHub keeps traffic for 14 days only. Run this once a day, from cron or launchd:

    python3 scripts/traffic_archive.py --output ~/openings-traffic/traffic.jsonl

Each line holds the day's views, clones, referrers and popular paths, the stars
with `starred_at`, the forks, open and closed issues by author, and the Docker
Hub pull count with its change since the previous line. A second run on the same
UTC day writes nothing. The repository is addressed by its numeric id, so a
rename does not break it. The token comes from `GITHUB_TOKEN` or `GH_TOKEN`, else
from `gh auth token`; it needs push access for the traffic endpoints and is never
written anywhere. The output must be outside this checkout: no traffic data is
ever committed. Standard library only.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ID = 1071590768  # VincenzoImp/openings-job-search
DOCKER_IMAGE = "vincenzoimp/openings"
OUTPUT = Path("~/.local/share/openings-traffic/traffic.jsonl")
GITHUB = "https://api.github.com"
DOCKER_HUB = "https://hub.docker.com/v2/repositories"


def http_fetch(url, headers):
    """GET a JSON document; returns it with the URL of the next page, if any."""
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        link = response.headers.get("Link") or ""
        data = json.load(response)
    found = re.search(r'<([^>]+)>;\s*rel="next"', link)
    return data, found and found.group(1)


def github_token():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    completed = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=False)
    if completed.returncode or not completed.stdout.strip():
        raise SystemExit("Set GITHUB_TOKEN or sign in with `gh auth login`.")
    return completed.stdout.strip()


def collect(repository_id, docker_image, previous, fetch, token):
    """The day's record, from the APIs through `fetch(url, headers)`."""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base = f"{GITHUB}/repositories/{repository_id}"

    def one(path, accept=None):
        return fetch(base + path, {**headers, "Accept": accept or headers["Accept"]})[0]

    def every(path, accept=None):
        items, url = [], f"{base}{path}{'&' if '?' in path else '?'}per_page=100"
        while url:
            page, url = fetch(url, {**headers, "Accept": accept or headers["Accept"]})
            items.extend(page)
        return items

    stars = every("/stargazers", "application/vnd.github.star+json")
    forks = every("/forks?sort=oldest")
    issues = defaultdict(lambda: {"open": 0, "closed": 0})
    for issue in every("/issues?state=all"):
        if "pull_request" not in issue:
            issues[(issue.get("user") or {}).get("login") or "ghost"][issue["state"]] += 1
    record = {
        "views": one("/traffic/views"),
        "clones": one("/traffic/clones"),
        "referrers": one("/traffic/popular/referrers"),
        "paths": one("/traffic/popular/paths"),
        "stars": [
            {"login": (star.get("user") or {}).get("login"), "starred_at": star["starred_at"]}
            for star in stars
        ],
        "forks": [{"name": fork["full_name"], "created_at": fork["created_at"]} for fork in forks],
        "issues": dict(sorted(issues.items())),
    }
    if docker_image:
        # Docker Hub gets no GitHub token. CI pulls inflate the total, so the
        # change per day is what to read.
        count = fetch(f"{DOCKER_HUB}/{docker_image}/", {"Accept": "application/json"})[0][
            "pull_count"
        ]
        before = ((previous or {}).get("docker") or {}).get("pull_count")
        record["docker"] = {
            "image": docker_image,
            "pull_count": count,
            "pull_count_delta": None if before is None else count - before,
        }
    return record


def read_entries(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main(argv=None, fetch=http_fetch, now=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repository-id", type=int, default=REPOSITORY_ID)
    parser.add_argument("--docker-image", default=DOCKER_IMAGE, help="'' skips Docker Hub")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    output = args.output.expanduser().resolve()
    if output.is_relative_to(ROOT):
        raise SystemExit(f"{output} is inside the checkout; write traffic data outside it.")
    now = now or datetime.datetime.now(datetime.UTC)
    day = now.date().isoformat()
    entries = read_entries(output)
    if any(entry.get("date") == day for entry in entries):
        print(f"{output}: {day} is already recorded.")
        return 0
    record = collect(
        args.repository_id,
        args.docker_image,
        entries[-1] if entries else None,
        fetch,
        github_token(),
    )
    entry = {
        "date": day,
        "recorded_at": now.isoformat(timespec="seconds"),
        "repository_id": args.repository_id,
        **record,
    }
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(output, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as file:
        file.write(json.dumps(entry, sort_keys=True) + "\n")
    print(f"{output}: recorded {day}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
