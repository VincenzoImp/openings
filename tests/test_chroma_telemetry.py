"""Tests for ChromaDB telemetry adapters."""

from __future__ import annotations


def test_noop_product_telemetry_client_matches_chroma_component_contract() -> None:
    """The no-op telemetry adapter must be safe for Chroma's component lifecycle."""
    from job_search_tool.chroma_telemetry import NoOpProductTelemetryClient

    client = NoOpProductTelemetryClient(system=object())

    client.capture(object())
    client.start()
    client.stop()
    client.reset_state()

    assert client.dependencies() == set()
