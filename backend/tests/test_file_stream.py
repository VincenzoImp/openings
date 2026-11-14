"""File snapshots preserve exact bytes without SQLite objects crossing threads."""

import asyncio

import pytest
from starlette.requests import ClientDisconnect

from openings.documents import UploadReservation
from openings.snapshots import SnapshotResponse


@pytest.mark.asyncio
async def test_file_stream_survives_thread_changes_and_original_deletion(
    app, client, alternating_threads
):
    workspace, documents = app.state.workspace, app.state.documents
    job = workspace.ingest_job({"title": "Synthetic role", "posting": "Build services."})
    content = b"Synthetic exact file bytes\n" * 10000
    grant = documents.reserve_upload(
        UploadReservation(
            owner_type="job",
            owner_id=job["id"],
            name="evidence.txt",
            size=len(content),
            media_type="text/plain",
        )
    )
    record = client.put(grant["url"], headers=grant["headers"], content=content).json()
    response = documents.file_response(record["id"])
    documents.delete_file(record["id"], 1)
    messages = []

    async def send(message):
        messages.append(message)

    async def receive():
        await asyncio.Event().wait()

    await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
    assert b"".join(message.get("body", b"") for message in messages) == content
    assert response.headers["content-length"] == str(len(content))
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"].startswith("sandbox;")
    assert response.snapshot.closed and len(alternating_threads) >= 3


@pytest.mark.asyncio
async def test_file_disconnect_releases_temporary_snapshot():
    response = SnapshotResponse(iter([b"x" * 200000]), media_type="application/pdf")

    async def send(message):
        if message["type"] == "http.response.body":
            raise OSError("Synthetic disconnected preview")

    async def receive():
        await asyncio.Event().wait()

    with pytest.raises(ClientDisconnect):
        await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
    assert response.snapshot.closed
