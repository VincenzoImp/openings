"""Public-address policy and the bounded, gated HTTP fetch used by every collection request."""

from __future__ import annotations

import ipaddress
import socket
from contextvars import ContextVar
from urllib.parse import urljoin, urlsplit

import httpcore
import httpx

from .. import __version__
from ..collectors.policy import ProviderBudget
from ..errors import DomainError

MAX_FEED_BYTES = 8 * 1024 * 1024


HTTP_BUDGET: ContextVar[ProviderBudget | None] = ContextVar("collection_http_budget", default=None)


def public_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise DomainError(
            422, "invalid_url", "Use a public HTTP(S) URL without embedded credentials."
        )
    public_addresses(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    return value


def is_public_address(address: str) -> bool:
    return ipaddress.ip_address(address).is_global


def public_addresses(host: str, port: int) -> list[str]:
    """Resolve a host once; every address must be public or the request is refused."""
    try:
        rows = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as error:
        raise DomainError(
            422, "unreachable_url", "The URL's host could not be resolved."
        ) from error
    addresses = list(dict.fromkeys(str(row[4][0]) for row in rows))
    if not addresses or not all(is_public_address(item) for item in addresses):
        raise DomainError(
            422, "private_url", "Collection URLs must resolve to public network addresses."
        )
    return addresses


class PublicNetworkBackend(httpcore.SyncBackend):
    """Connect only to the public addresses checked for this connection.

    Resolving inside the connection and dialing the checked IP closes the DNS
    rebinding window between the URL check and httpx's own name resolution. TLS
    still verifies the certificate against the requested host name.
    """

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        failure = None
        for address in public_addresses(host, port):
            try:
                return super().connect_tcp(address, port, timeout, local_address, socket_options)
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as error:
                failure = error
        raise failure


class PublicTransport(httpx.HTTPTransport):
    """An httpx transport whose every connection, including redirect hops, is pinned."""

    def __init__(self):
        super().__init__(trust_env=False)
        limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
        self._pool = httpcore.ConnectionPool(
            ssl_context=httpx.create_ssl_context(trust_env=False),
            max_connections=limits.max_connections,
            max_keepalive_connections=limits.max_keepalive_connections,
            keepalive_expiry=limits.keepalive_expiry,
            network_backend=PublicNetworkBackend(),
        )


def fetch_bytes(
    url: str,
    *,
    public: bool = True,
    maximum: int = MAX_FEED_BYTES,
    budget: ProviderBudget | None = None,
    method="GET",
    body=None,
) -> bytes:
    budget = budget or HTTP_BUDGET.get()
    current = url
    try:
        with httpx.Client(
            timeout=httpx.Timeout(20, connect=8),
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": f"Openings/{__version__} (job archive)"},
            transport=PublicTransport() if public else None,
        ) as client:
            for _ in range(5):
                if public:
                    public_url(current)
                if budget:
                    budget.before(method, current)
                try:
                    response_context = (
                        client.stream(method, current, json=body)
                        if body is not None
                        else client.stream(method, current)
                    )
                    response = response_context.__enter__()
                except httpx.HTTPError as error:
                    if budget:
                        budget.after(None, error=type(error).__name__)
                    raise
                except DomainError as error:
                    # The connection-time address check refused this hop.
                    if budget:
                        budget.after(None, error=error.code)
                    raise
                try:
                    if budget:
                        budget.after(response.status_code, response.headers)
                        if budget.blocked:
                            raise budget.blocked
                    if response.is_redirect:
                        target = response.headers.get("location")
                        if not target:
                            raise DomainError(
                                502, "source_redirect", "The source returned an invalid redirect."
                            )
                        current = urljoin(current, target)
                        if response.status_code == 303 or (
                            response.status_code in (301, 302) and method == "POST"
                        ):
                            method, body = "GET", None
                        continue
                    response.raise_for_status()
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > maximum:
                            raise DomainError(
                                422,
                                "source_too_large",
                                "This feed exceeds the bounded collection size.",
                            )
                    return bytes(content)
                finally:
                    response_context.__exit__(None, None, None)
    except httpx.HTTPStatusError as error:
        raise DomainError(
            502,
            "source_http",
            f"The source returned HTTP {error.response.status_code}.",
            {"http_status": error.response.status_code},
        ) from error
    except httpx.HTTPError as error:
        raise DomainError(
            502, "source_unavailable", "The source could not be reached. Try again later."
        ) from error
    raise DomainError(422, "source_redirect", "The source redirected too many times.")
