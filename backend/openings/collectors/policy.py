"""One transactional HTTP gate for scheduled, manual and preview acquisition.

Limits are conservative owner-configurable safeguards, not provider guarantees.
Reservations count attempted requests (including transport failures). Runtime is
stored in SQLite, so restarting the process cannot reset a window or cooldown.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit

from pydantic import BaseModel, ConfigDict, Field

from ..common import check_version, encode, new_id, now
from ..errors import DomainError, missing

COMPANY_KINDS = (
    "greenhouse",
    "lever",
    "ashby",
    "recruitee",
    "personio",
    "workable",
    "breezy",
    "smartrecruiters",
    "bamboohr",
    "rippling",
    "workday",
    "oracle",
    "joincom",
)
PROVIDERS = {
    **{
        kind: (
            kind.title(),
            "company",
            "Public company board; bounded listing and detail requests.",
        )
        for kind in COMPANY_KINDS
    },
    "linkedin": ("LinkedIn", "search", "JobSpy 1.4.1 public search and optional posting details."),
    "indeed": ("Indeed", "search", "JobSpy 1.4.1 public search; country support varies."),
    "glassdoor": (
        "Glassdoor",
        "search",
        "JobSpy 1.4.1 search, location lookup and optional batched details.",
    ),
    "jobcloud": (
        "JobCloud",
        "search",
        "Public jobs.ch/jobup.ch regional search; undocumented endpoint.",
    ),
    "adzuna": (
        "Adzuna",
        "search",
        "Optional owner-supplied API credentials required; snippets only.",
    ),
    "rss": ("RSS / Atom", "feed", "Explicit feed URL; locations absent from feeds remain unknown."),
    "manual": (
        "Manual URL / board detection",
        "manual",
        "Public URL import and explicit ATS board detection.",
    ),
    "google": (
        "Google Jobs",
        "unsupported",
        "Unsupported: usable job data was unavailable in the verified JobSpy provider.",
    ),
}


def provider_for_url(value: str) -> str:
    """Choose the same provider gate for a known public board/posting host."""
    host = (urlsplit(value).hostname or "").lower()
    suffixes = {
        "linkedin.com": "linkedin",
        "indeed.com": "indeed",
        "glassdoor.com": "glassdoor",
        "greenhouse.io": "greenhouse",
        "lever.co": "lever",
        "ashbyhq.com": "ashby",
        "recruitee.com": "recruitee",
        "jobs.personio.de": "personio",
        "workable.com": "workable",
        "breezy.hr": "breezy",
        "bamboohr.com": "bamboohr",
        "smartrecruiters.com": "smartrecruiters",
        "rippling.com": "rippling",
        "myworkdayjobs.com": "workday",
        "oraclecloud.com": "oracle",
        "join.com": "joincom",
        "jobs.ch": "jobcloud",
        "jobup.ch": "jobcloud",
        "adzuna.com": "adzuna",
    }
    return next(
        (
            provider
            for suffix, provider in suffixes.items()
            if host == suffix or host.endswith("." + suffix)
        ),
        "manual",
    )


class ProviderPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool = True
    min_interval_seconds: float = Field(default=3.0, ge=0, le=3600)
    max_requests_per_hour: int = Field(default=100, ge=1, le=10000)
    max_requests_per_day: int = Field(default=500, ge=1, le=10000)
    max_requests_per_run: int = Field(default=40, ge=1, le=200)


class ProviderPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_version: int = Field(ge=1)
    enabled: bool | None = None
    min_interval_seconds: float | None = Field(default=None, ge=0, le=3600)
    max_requests_per_hour: int | None = Field(default=None, ge=1, le=10000)
    max_requests_per_day: int | None = Field(default=None, ge=1, le=10000)
    max_requests_per_run: int | None = Field(default=None, ge=1, le=200)


def iso(moment: float) -> str:
    return datetime.fromtimestamp(moment, timezone.utc).isoformat(timespec="microseconds")


def epoch(value) -> float:
    return datetime.fromisoformat(value).timestamp() if value else 0.0


def retry_after(value: str | None, moment: float) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value)
        if seconds >= 0 and seconds < float("inf"):
            return moment + seconds
    except (TypeError, ValueError):
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return max(moment, parsed.timestamp())
        except (ValueError, TypeError, OverflowError):
            pass
    return None


class ProviderDeferred(DomainError):
    def __init__(self, provider, reason, next_run_at=None):
        super().__init__(
            429,
            reason,
            f"{PROVIDERS[provider][0]}: {reason.replace('_', ' ')}.",
            {"provider": provider, "next_run_at": next_run_at},
        )
        self.provider = provider
        self.next_run_at = next_run_at


class ProviderStore:
    def __init__(self, db):
        self.db = db
        with db.transaction() as connection:
            for provider in PROVIDERS:
                policy = ProviderPolicy(enabled=provider not in ("google", "adzuna")).model_dump()
                connection.execute(
                    "INSERT OR IGNORE INTO providers(id,policy,runtime,updated_at) VALUES(?,?,?,?)",
                    (provider, encode(policy), "{}", now()),
                )

    def _row(self, provider):
        if provider not in PROVIDERS:
            missing("Provider")
        return self.db.one("SELECT * FROM providers WHERE id=?", (provider,))

    def get(self, provider):
        row = self._row(provider)
        policy, runtime = json.loads(row["policy"]), json.loads(row["runtime"])
        moment = time.time()
        events = runtime.get("events", [])
        name, kind, description = PROVIDERS[provider]
        public_runtime = {
            key: runtime.get(key)
            for key in (
                "next_allowed_at",
                "cooldown_until",
                "last_request_at",
                "last_status",
                "last_error",
            )
        }
        public_runtime.update(
            {
                "requests_hour": sum(moment - 3600 < value <= moment for value in events),
                "requests_day": sum(moment - 86400 < value <= moment for value in events),
                "total_requests": runtime.get("total_requests", 0),
            }
        )
        targets = [epoch(runtime.get(key)) for key in ("next_allowed_at", "cooldown_until")]
        day = [value for value in events if value > moment - 86400]
        hour = [value for value in day if value > moment - 3600]
        for values, maximum, window in (
            (day, policy["max_requests_per_day"], 86400),
            (hour, policy["max_requests_per_hour"], 3600),
        ):
            if len(values) >= maximum:
                targets.append(values[-maximum] + window)
        if max(targets, default=0):
            public_runtime["next_allowed_at"] = iso(max(targets))
        return {
            "id": provider,
            "name": name,
            "capability": {
                "supported": provider != "google",
                "kind": kind,
                "description": description,
                "transport_version": "jobspy1.4.1-openings1"
                if provider in ("linkedin", "indeed", "glassdoor")
                else "openings1",
                "credentials_required": provider == "adzuna",
            },
            "policy": policy,
            "runtime": public_runtime,
            "version": row["version"],
            "updated_at": row["updated_at"],
        }

    def list(self):
        return {"items": [self.get(provider) for provider in PROVIDERS], "total": len(PROVIDERS)}

    def update(self, provider, value: ProviderPatch):
        self._row(provider)
        updates = value.model_dump(exclude_unset=True, exclude={"expected_version"})
        if any(value is None for value in updates.values()):
            raise DomainError(422, "provider_policy", "Provider policy values cannot be null.")
        if provider == "google" and updates.get("enabled"):
            raise DomainError(422, "unsupported_provider", PROVIDERS[provider][2])
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM providers WHERE id=?", (provider,)).fetchone()
            check_version(row, value.expected_version)
            policy = ProviderPolicy.model_validate({**json.loads(row["policy"]), **updates})
            connection.execute(
                "UPDATE providers SET policy=?,version=version+1,updated_at=? WHERE id=?",
                (encode(policy.model_dump()), now(), provider),
            )
        return self.get(provider)


class ProviderBudget:
    """Per-instance request hook, also usable by the manual URL importer.

    `request(send, method, url, **kwargs)` wraps requests/curl compatible senders.
    HTTPX streaming callers can use `before`/`after` around each attempt instead.
    Tiny pacing waits belong to the dedicated collection lane. Long windows
    raise ProviderDeferred and are persisted on the task rather than sleeping.
    """

    def __init__(self, store, provider, run_id=None, active=None, validate_url=None, max_wait=5):
        store._row(provider)
        self.store, self.provider = store, provider
        self.run_id = run_id or new_id()
        self.active = active
        self.validate_url = validate_url
        self.max_wait = max_wait
        self.requests = 0
        self.responses = []
        self.blocked = None

    def _check_active(self):
        if self.active is not None and not self.active():
            self.blocked = DomainError(409, "task_cancelled", "Collection was cancelled.")
            raise self.blocked

    def before(self, method, url):
        self._check_active()
        target_provider = provider_for_url(url)
        if target_provider not in ("manual", self.provider):
            raise DomainError(
                422,
                "provider_redirect",
                f"This URL targets another provider: {url}. Import that destination URL directly so its provider policy is applied.",
                {
                    "provider": self.provider,
                    "destination_provider": target_provider,
                    "destination_url": url,
                },
            )
        if self.blocked is not None:
            raise self.blocked
        started = time.monotonic()
        while True:
            moment = time.time()
            wait_until, reason = moment, "provider_interval"
            with self.store.db.transaction() as connection:
                row = connection.execute(
                    "SELECT * FROM providers WHERE id=?", (self.provider,)
                ).fetchone()
                policy, runtime = json.loads(row["policy"]), json.loads(row["runtime"])
                if self.provider == "google":
                    raise DomainError(422, "unsupported_provider", PROVIDERS[self.provider][2])
                if not policy["enabled"]:
                    self.blocked = ProviderDeferred(self.provider, "provider_paused")
                    raise self.blocked
                events = [value for value in runtime.get("events", []) if value > moment - 86400]
                hour = [value for value in events if value > moment - 3600]
                runs = runtime.get("runs", {})
                run_count = runs.get(self.run_id, {}).get("count", 0)
                if run_count >= policy["max_requests_per_run"]:
                    self.blocked = ProviderDeferred(self.provider, "provider_run_budget")
                    raise self.blocked
                if len(events) >= policy["max_requests_per_day"]:
                    wait_until, reason = (
                        events[-policy["max_requests_per_day"]] + 86400,
                        "provider_day_budget",
                    )
                if len(hour) >= policy["max_requests_per_hour"]:
                    target = hour[-policy["max_requests_per_hour"]] + 3600
                    if target > wait_until:
                        wait_until, reason = target, "provider_hour_budget"
                for key, why in (
                    ("next_allowed_at", "provider_interval"),
                    ("cooldown_until", "provider_cooldown"),
                ):
                    target = epoch(runtime.get(key))
                    if target > wait_until:
                        wait_until, reason = target, why
                if wait_until <= moment:
                    events.append(moment)
                    runs[self.run_id] = {"count": run_count + 1, "at": moment}
                    runs = dict(sorted(runs.items(), key=lambda pair: pair[1]["at"])[-200:])
                    runtime.update(
                        {
                            "events": events,
                            "runs": runs,
                            "total_requests": runtime.get("total_requests", 0) + 1,
                            "last_request_at": iso(moment),
                            "next_allowed_at": iso(moment + policy["min_interval_seconds"]),
                        }
                    )
                    connection.execute(
                        "UPDATE providers SET runtime=?,updated_at=? WHERE id=?",
                        (encode(runtime), now(), self.provider),
                    )
                    self.requests += 1
                    return
            wait = wait_until - moment
            if reason != "provider_interval" or wait + time.monotonic() - started > self.max_wait:
                self.blocked = ProviderDeferred(self.provider, reason, iso(wait_until))
                raise self.blocked
            until = time.monotonic() + wait
            while time.monotonic() < until:
                self._check_active()
                time.sleep(min(0.1, max(0, until - time.monotonic())))

    def after(self, status, headers=None, error=None):
        moment = time.time()
        headers = {key.lower(): value for key, value in (headers or {}).items()}
        with self.store.db.transaction() as connection:
            row = connection.execute(
                "SELECT runtime FROM providers WHERE id=?", (self.provider,)
            ).fetchone()
            runtime = json.loads(row["runtime"])
            runtime["last_status"] = status
            runtime["last_error"] = (
                str(error)[:300]
                if error
                else (f"HTTP {status}" if status and status >= 400 else None)
            )
            target = retry_after(headers.get("retry-after"), moment)
            if status == 429:
                count = runtime.get("throttle_count", 0) + 1
                runtime["throttle_count"] = count
                target = (
                    target
                    if target is not None
                    else moment + min(3600, 60 * 2 ** min(count - 1, 6))
                )
            elif status and 200 <= status < 300:
                runtime["throttle_count"] = 0
            if target is not None and (status == 429 or status == 503):
                target = max(target, epoch(runtime.get("cooldown_until")))
                runtime["cooldown_until"] = iso(target)
                self.blocked = ProviderDeferred(self.provider, "provider_cooldown", iso(target))
            connection.execute(
                "UPDATE providers SET runtime=?,updated_at=? WHERE id=?",
                (encode(runtime), now(), self.provider),
            )
        self.responses.append({"status": status, "retry_after": headers.get("retry-after")})

    def request(self, send, method, url, **kwargs):
        kwargs["allow_redirects"] = False
        owner = getattr(send, "__self__", None)
        is_curl = any(cls.__module__.startswith("curl_cffi") for cls in type(owner).__mro__)
        current = url
        for _ in range(6):
            if self.validate_url:
                self.validate_url(current)
            self.before(method, current)
            content = bytearray()
            overflow = False

            def receive(chunk):
                nonlocal overflow
                if self.active is not None and not self.active():
                    return 0xFFFFFFFF  # CURL_WRITEFUNC_ERROR; stop this transfer.
                if len(content) + len(chunk) > 8 * 1024 * 1024:
                    overflow = True
                    return 0xFFFFFFFF
                content.extend(chunk)
                return len(chunk)

            # curl's content callback bounds the transfer without an unbounded
            # background stream queue. requests uses a synchronous bounded read.
            kwargs["content_callback" if is_curl else "stream"] = receive if is_curl else True
            try:
                response = send(method, current, **kwargs)
            except Exception as error:
                failed = getattr(error, "response", None)
                self.after(
                    getattr(failed, "status_code", None),
                    getattr(failed, "headers", None),
                    error=type(error).__name__,
                )
                self._check_active()
                if overflow:
                    raise DomainError(
                        422,
                        "source_too_large",
                        "This portal response exceeds the bounded collection size.",
                    ) from error
                raise
            self.after(response.status_code, response.headers)
            if self.blocked:
                response.close()
                raise self.blocked
            if response.status_code in (301, 302, 303, 307, 308) and response.headers.get(
                "location"
            ):
                current = urljoin(current, response.headers["location"])
                response.close()
                kwargs.pop("params", None)
                if response.status_code == 303 or (
                    response.status_code in (301, 302) and method.upper() == "POST"
                ):
                    method = "GET"
                    kwargs.pop("json", None)
                    kwargs.pop("data", None)
                continue
            if is_curl:
                response.content = bytes(content)
            else:
                try:
                    for chunk in response.iter_content(chunk_size=65536):
                        self._check_active()
                        if len(content) + len(chunk) > 8 * 1024 * 1024:
                            raise DomainError(
                                422,
                                "source_too_large",
                                "This portal response exceeds the bounded collection size.",
                            )
                        content.extend(chunk)
                    response._content = bytes(content)
                    response._content_consumed = True
                finally:
                    response.close()
            return response
        raise DomainError(422, "source_redirect", "The source redirected too many times.")

    def diagnostics(self):
        blocked = self.blocked
        return {
            "provider": self.provider,
            "state": "deferred" if blocked else "ok",
            "message": blocked.message if blocked else None,
            "requests": self.requests,
            "responses": self.responses,
            "next_run_at": getattr(blocked, "next_run_at", None),
        }
