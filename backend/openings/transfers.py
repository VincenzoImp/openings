"""Close SQLite readers on their owning thread before serving portable byte snapshots."""

import tempfile

from fastapi.responses import StreamingResponse


class SnapshotResponse(StreamingResponse):
    def __init__(self, content, *, media_type, headers=None):
        self.snapshot = tempfile.TemporaryFile()  # noqa: SIM115 - closed after streaming
        try:
            for chunk in content:
                self.snapshot.write(chunk)
            size = self.snapshot.tell()
            self.snapshot.seek(0)

            def chunks():
                while chunk := self.snapshot.read(64 * 1024):
                    yield chunk

            super().__init__(
                chunks(),
                media_type=media_type,
                headers={**(headers or {}), "Content-Length": str(size)},
            )
        except BaseException:
            self.snapshot.close()
            raise

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.snapshot.close()
