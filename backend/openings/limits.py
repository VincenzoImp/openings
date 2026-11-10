"""Count request body bytes as they arrive instead of trusting Content-Length."""

import json

REQUEST_LIMIT = 40 * 1024**2
AUTH_LIMIT = 16 * 1024
TOO_LARGE = json.dumps(
    {
        "error": {
            "code": "request_size",
            "message": "This request exceeds the upload limit.",
            "details": None,
        }
    }
).encode()


class BodyLimit:
    """ASGI middleware; restore streams under its own installation limit.

    Body parsers turn receive errors into generic 400s, so the limit answers
    413 itself, reports a disconnect to the app and drops the app's response.
    """

    def __init__(self, app):
        self.app = app

    @staticmethod
    def limit(path: str):
        path = path.rstrip("/")
        if path == "/api/v1/backup/restore":
            return None
        if path.startswith("/api/v1/auth/"):
            return AUTH_LIMIT
        return REQUEST_LIMIT

    async def __call__(self, scope, receive, send):
        limit = self.limit(scope.get("path", "")) if scope["type"] == "http" else None
        if limit is None:
            return await self.app(scope, receive, send)
        received, started, rejected = 0, False, False

        async def guarded_send(message):
            nonlocal started
            if rejected:
                return
            started = started or message["type"] == "http.response.start"
            await send(message)

        async def counted():
            nonlocal received, rejected
            if rejected:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    if not started:
                        await send(
                            {
                                "type": "http.response.start",
                                "status": 413,
                                "headers": [
                                    (b"content-type", b"application/json"),
                                    (b"content-length", str(len(TOO_LARGE)).encode()),
                                ],
                            }
                        )
                        await send({"type": "http.response.body", "body": TOO_LARGE})
                    rejected = True
                    return {"type": "http.disconnect"}
            return message

        await self.app(scope, counted, guarded_send)
