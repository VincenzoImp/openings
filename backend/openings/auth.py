"""One owner session and separately revocable API/MCP bearer tokens."""

import base64
import hashlib
import hmac
import os
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .common import new_id, now
from .errors import DomainError

COOKIE = "openings_session"
MAX_AGE = 7 * 24 * 3600


def password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    raw = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return base64.b64encode(salt).decode() + ":" + base64.b64encode(raw).decode()


def password_matches(password, encoded):
    try:
        salt = base64.b64decode(encoded.split(":")[0])
        return hmac.compare_digest(password_hash(password, salt), encoded)
    except (ValueError, TypeError):
        return False


class Auth:
    def __init__(self, workspace):
        self.workspace = workspace
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

    def serializer(self):
        data = self.workspace.get_settings("auth")["data"]
        return URLSafeTimedSerializer(data.get("secret", "unconfigured"), salt="openings-owner-v1")

    def login(self, password):
        if not password_matches(
            password, self.workspace.get_settings("auth")["data"].get("password_hash", "")
        ):
            raise DomainError(401, "login_failed", "The password is incorrect.")
        session = {"owner": True, "csrf": secrets.token_urlsafe(24)}
        return self.serializer().dumps(session), session

    def session(self, request):
        value = request.cookies.get(COOKIE)
        if not value or not self.configured():
            return None
        try:
            data = self.serializer().loads(value, max_age=MAX_AGE)
            return data if data.get("owner") else None
        except (BadSignature, SignatureExpired):
            return None

    def bearer(self, request):
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            return False
        token_hash = hashlib.sha256(header[7:].encode()).hexdigest()
        row = self.workspace.db.one("SELECT id FROM api_tokens WHERE token_hash=?", (token_hash,))
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

    def operation_ticket(self, operation):
        return self.serializer().dumps({"operation": operation, "nonce": secrets.token_urlsafe(16)})

    def authorize_operation(self, token, operation):
        try:
            value = self.serializer().loads(token, max_age=120)
        except (BadSignature, SignatureExpired):
            raise DomainError(
                401, "transfer_expired", "The operation grant expired. Request another."
            )
        if value.get("operation") != operation:
            raise DomainError(403, "transfer_scope", "This grant does not allow that operation.")
