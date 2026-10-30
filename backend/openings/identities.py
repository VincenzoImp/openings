"""Exact source and URL identities; no similarity-based job matching."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_url(url):
    if not url:
        return ""
    p = urlsplit(url.strip())
    query = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=True)
        if not k.lower().startswith("utm_")
        and k.lower() not in {"gclid", "fbclid", "ref", "source"}
    ]
    return urlunsplit(
        (
            p.scheme.lower(),
            p.netloc.lower(),
            p.path.rstrip("/") or "/",
            urlencode(sorted(query)),
            "",
        )
    )


def posting_identity(url):
    p = urlsplit(url)
    parts = [s for s in p.path.split("/") if s]
    host = (p.hostname or "").lower()
    if (
        host in {"boards.greenhouse.io", "job-boards.greenhouse.io"}
        and len(parts) >= 3
        and parts[1] == "jobs"
    ):
        return f"greenhouse:{parts[0]}:{parts[2]}"
    if host in {"jobs.lever.co", "jobs.eu.lever.co"} and len(parts) >= 2:
        return f"lever:{parts[0]}:{parts[1]}"
    if host == "jobs.ashbyhq.com" and len(parts) >= 2:
        return f"ashby:{parts[0]}:{parts[1]}"
    return "url:" + normalize_url(url) if url else None


def job_identities(url="", source_key=None):
    """Retain both the exact URL and a verified adapter/user-supplied source key."""
    return list(
        dict.fromkeys(
            value
            for value in (
                source_key,
                posting_identity(url),
                "url:" + normalize_url(url) if url else None,
            )
            if value
        )
    )
