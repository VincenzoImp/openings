"""One owner session and separately revocable API/MCP bearer tokens."""

import base64
import hashlib
import hmac
import math
import os
import secrets
import threading
import time
from collections import deque

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .common import new_id, now
from .errors import DomainError

COOKIE = "openings_session"
MAX_AGE = 7 * 24 * 3600
OPERATION_MAX_AGE = 120


def password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    raw = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return base64.b64encode(salt).decode() + ":" + base64.b64encode(raw).decode()


def password_matches(password, encoded):
    try:
        salt = base64.b64decode(encoded.split(":")[0])
        return hmac.compare_digest(password_hash(password, salt), encoded)
    except ValueError, TypeError:
        return False


class Auth:
    def __init__(self, workspace):
        self.workspace = workspace
        self.used_operations = UsedNonces()
        password = os.environ.get("OPENINGS_PASSWORD")
        if password and not self.configured():
            self.setup(password)

    def configured(self):
        return bool(self.workspace.get_settings("auth")["data"].get("password_hash"))

    def setup(self, password):
        if len(password) < 10 or len(password) > 1024:
            raise DomainError(422, "password_length", "Use a password of at least 10 characters.")
        with self.workspace.db.lock:
            if self.configured():
                raise DomainError(409, "already_configured", "This workspace already has an owner.")
            self.workspace.set_settings(
                "auth", {"password_hash": password_hash(password), "secret": secrets.token_hex(32)}
            )

    def change_password(self, password):
        if not 10 <= len(password) <= 1024:
            raise DomainError(422, "password_length", "Use a password of at least 10 characters.")
        with self.workspace.db.lock:
            if not self.configured():
                raise DomainError(409, "not_configured", "Set up the workspace owner first.")
            self.workspace.set_settings(
                "auth", {"password_hash": password_hash(password), "secret": secrets.token_hex(32)}
            )
        return {"updated": True, "sign_in_required": True, "api_tokens_preserved": True}

    def serializer(self, data=None):
        data = self.workspace.get_settings("auth")["data"] if data is None else data
        return URLSafeTimedSerializer(data.get("secret", "unconfigured"), salt="openings-owner-v1")

    def login(self, password):
        data = self.workspace.get_settings("auth")["data"]
        if not password_matches(password, data.get("password_hash", "")):
            raise DomainError(401, "login_failed", "The password is incorrect.")
        session = {
            "owner": True,
            "csrf": secrets.token_urlsafe(24),
            "generation": data.get("session_generation", 0),
        }
        return self.serializer(data).dumps(session), session

    def session(self, request):
        value = request.cookies.get(COOKIE)
        data = self.workspace.get_settings("auth")["data"]
        if not value or not data.get("password_hash"):
            return None
        try:
            session = self.serializer(data).loads(value, max_age=MAX_AGE)
        except BadSignature, SignatureExpired:
            return None
        # A logout increments the stored generation, revoking every earlier cookie.
        if not session.get("owner") or session.get("generation", 0) != data.get(
            "session_generation", 0
        ):
            return None
        return session

    def logout(self):
        """Revoke every browser session; API/MCP tokens remain valid."""
        with self.workspace.db.lock:
            setting = self.workspace.get_settings("auth")
            data = setting["data"]
            if data.get("password_hash"):
                self.workspace.set_settings(
                    "auth",
                    {**data, "session_generation": data.get("session_generation", 0) + 1},
                    setting["version"],
                )
        return {"authenticated": False, "sessions_revoked": True, "api_tokens_preserved": True}

    def bearer(self, request):
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            return False
        token_hash = hashlib.sha256(header[7:].encode()).hexdigest()
        row = self.workspace.db.one(
            "SELECT id,last_used_at FROM api_tokens WHERE token_hash=?", (token_hash,)
        )
        if row:
            stamp = now()
            # Record useful usage metadata without a write on every agent request.
            if not row["last_used_at"] or row["last_used_at"][:13] != stamp[:13]:
                self.workspace.db.execute(
                    "UPDATE api_tokens SET last_used_at=? WHERE id=?", (stamp, row["id"])
                )
        return bool(row)

    def authorize(self, request, mcp=False):
        if self.bearer(request):
            return
        session = None if mcp else self.session(request)
        if not session:
            raise DomainError(401, "unauthorized", "Sign in or provide an API token.")
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            supplied = request.headers.get("x-csrf-token", "")
            if not hmac.compare_digest(supplied, session["csrf"]):
                raise DomainError(403, "csrf", "The session changed. Reload and try again.")

    def list_tokens(self):
        rows = self.workspace.db.all(
            "SELECT id,name,created_at,last_used_at FROM api_tokens ORDER BY created_at DESC"
        )
        return {"items": rows, "total": len(rows)}

    def create_token(self, name):
        token, record_id = "op_" + secrets.token_urlsafe(32), new_id()
        self.workspace.db.execute(
            "INSERT INTO api_tokens(id,name,token_hash,created_at) VALUES(?,?,?,?)",
            (record_id, name, hashlib.sha256(token.encode()).hexdigest(), now()),
        )
        return {"id": record_id, "name": name, "token": token, "created_at": now()}

    def revoke_token(self, record_id):
        self.workspace.db.execute("DELETE FROM api_tokens WHERE id=?", (record_id,))
        return {"deleted": True}

    def operation_serializer(self):
        """Operational grants use their own salt, so they never verify as sessions."""
        secret = self.workspace.get_settings("auth")["data"].get("secret", "unconfigured")
        return URLSafeTimedSerializer(secret, salt="openings-operation-v1")

    def operation_ticket(self, operation):
        return self.operation_serializer().dumps(
            {"operation": operation, "nonce": secrets.token_urlsafe(16)}
        )

    def authorize_operation(self, token, operation):
        try:
            value = self.operation_serializer().loads(token, max_age=OPERATION_MAX_AGE)
        except BadSignature, SignatureExpired:
            raise DomainError(
                401, "transfer_expired", "The operation grant expired. Request another."
            )
        if not isinstance(value, dict) or value.get("operation") != operation:
            raise DomainError(403, "transfer_scope", "This grant does not allow that operation.")
        self.used_operations.consume(str(value.get("nonce", "")))


class UsedNonces:
    """Single-use grant nonces, remembered in memory until their grant expires."""

    def __init__(self, max_age=OPERATION_MAX_AGE, clock=time.monotonic):
        self.max_age, self.clock = max_age, clock
        self.expiries = {}
        self.lock = threading.Lock()

    def consume(self, nonce):
        stamp = self.clock()
        with self.lock:
            for key in [key for key, expiry in self.expiries.items() if expiry <= stamp]:
                del self.expiries[key]
            if not nonce or nonce in self.expiries:
                raise DomainError(
                    401, "transfer_used", "This operation grant was already used. Request another."
                )
            # A grant signed up to max_age ago cannot verify after this expiry.
            self.expiries[nonce] = stamp + self.max_age + 1


class LoginGuard:
    """Per-client attempt limits plus a bounded global backoff after failed logins.

    Each client may try ``per_client`` times per ``window`` seconds. After
    ``free_failures`` failed logins across all clients within ``failure_window``
    seconds, login attempts are spaced globally by a delay that doubles with each
    further failure up to ``max_delay``. Attempts queue for their slot instead of
    being refused, so the owner still gets a turn; an attempt that would wait more
    than ``max_wait`` seconds is refused with a retry time. A successful login
    clears the global backoff.
    """

    def __init__(
        self,
        *,
        per_client=10,
        window=60,
        free_failures=10,
        failure_window=900,
        max_delay=5,
        max_wait=30,
        max_clients=4096,
        clock=time.monotonic,
    ):
        self.per_client, self.window = per_client, window
        self.free_failures, self.failure_window = free_failures, failure_window
        self.max_delay, self.max_wait, self.max_clients = max_delay, max_wait, max_clients
        self.clock = clock
        self.clients = {}
        self.failures = deque()
        self.next_slot = 0.0

    def delay(self, stamp=None):
        stamp = self.clock() if stamp is None else stamp
        while self.failures and self.failures[0] <= stamp - self.failure_window:
            self.failures.popleft()
        excess = len(self.failures) - self.free_failures
        return 0 if excess <= 0 else min(self.max_delay, 2 ** min(excess - 1, 16))

    def admit(self, client, login=True):
        """Record one attempt and return the seconds to wait before checking it."""
        stamp = self.clock()
        attempts = self.clients.get(client)
        if attempts is None:
            if len(self.clients) >= self.max_clients:
                self._prune(stamp)
            attempts = self.clients[client] = deque()
        while attempts and attempts[0] <= stamp - self.window:
            attempts.popleft()
        if len(attempts) >= self.per_client:
            retry = math.ceil(attempts[0] + self.window - stamp)
            raise DomainError(
                429,
                "login_rate",
                "Too many attempts. Try again in a minute.",
                {"retry_after_seconds": max(retry, 1)},
            )
        wait = 0.0
        delay = self.delay(stamp) if login else 0
        if delay:
            slot = max(stamp, self.next_slot)
            wait = slot - stamp
            if wait > self.max_wait:
                raise DomainError(
                    429,
                    "login_backoff",
                    "Many sign-in attempts failed recently. Try again shortly.",
                    {"retry_after_seconds": math.ceil(wait - self.max_wait)},
                )
            self.next_slot = slot + delay
        attempts.append(stamp)
        return wait

    def failed(self):
        self.failures.append(self.clock())
        if len(self.failures) > 10_000:
            self.failures.popleft()

    def succeeded(self):
        self.failures.clear()
        self.next_slot = 0.0

    def _prune(self, stamp):
        for key in [
            key
            for key, attempts in self.clients.items()
            if not attempts or attempts[-1] <= stamp - self.window
        ]:
            del self.clients[key]
        while len(self.clients) >= self.max_clients:
            del self.clients[next(iter(self.clients))]
