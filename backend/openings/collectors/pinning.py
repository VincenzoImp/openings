"""Checked-address connections for the requests and curl provider sessions.

URL fetches through httpx dial the address that passed the public-address check
(`discovery.PublicNetworkBackend`). Provider sessions get the same policy here:
`resolve(host, port)` returns the checked addresses or refuses the host, and the
connection is made to one of those addresses. No second name lookup can swap
in another destination, while TLS still verifies the requested host name.

Both pins cover direct connections. Openings configures no proxy for provider
sessions and disables environment proxies on them.
"""

import ipaddress
from urllib.parse import urlsplit

from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import ConnectTimeoutError, NewConnectionError


def _pinned_pools(resolve):
    class Pinned:
        def _new_conn(self):
            host, failure = self._dns_host, None
            for address in resolve(host, self.port):
                # Dial the checked address; `host` stays the TLS/Host identity.
                self._dns_host = address
                try:
                    return super()._new_conn()
                except (NewConnectionError, ConnectTimeoutError) as error:
                    failure = error
                finally:
                    self._dns_host = host
            raise failure

    class PinnedHTTPConnection(Pinned, HTTPConnection):
        pass

    class PinnedHTTPSConnection(Pinned, HTTPSConnection):
        pass

    class PinnedHTTPPool(HTTPConnectionPool):
        ConnectionCls = PinnedHTTPConnection

    class PinnedHTTPSPool(HTTPSConnectionPool):
        ConnectionCls = PinnedHTTPSConnection

    return {"http": PinnedHTTPPool, "https": PinnedHTTPSPool}


class PinnedAdapter(HTTPAdapter):
    """A requests adapter whose every new connection uses a checked address."""

    def __init__(self, resolve, **kwargs):
        self.resolve = resolve
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = _pinned_pools(self.resolve)


def curl_resolve_entry(url, resolve):
    """The CURLOPT_RESOLVE entry binding the URL's host to its checked addresses.

    A literal address needs no entry: curl dials it as written once it is checked.
    """
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = resolve(host, port)
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pinned = ",".join(f"[{item}]" if ":" in item else item for item in addresses)
        return f"{host}:{port}:{pinned}"
    return None


def pin_session(session, url, resolve, *, is_curl):
    """Pin the session's next request to `url`; raises when the host is refused."""
    if is_curl:
        from curl_cffi import CurlOpt

        # Session options are applied to every request, so each attempt and
        # redirect hop replaces the previous entry with freshly checked addresses.
        entry = curl_resolve_entry(url, resolve)
        session.curl_options.pop(CurlOpt.RESOLVE, None)
        if entry:
            session.curl_options[CurlOpt.RESOLVE] = [entry]
    elif hasattr(session, "mount") and not isinstance(
        session.adapters.get("https://"), PinnedAdapter
    ):
        # requests resolves when it opens a connection; the adapter checks there.
        adapter = PinnedAdapter(resolve)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
