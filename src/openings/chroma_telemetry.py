"""ChromaDB telemetry adapters used by the local vector store."""

from __future__ import annotations


class NoOpProductTelemetryClient:
    """ChromaDB product-telemetry client that intentionally drops all events.

    ChromaDB 0.6.x still instantiates its PostHog client when only
    ``anonymized_telemetry=False`` is set, and recent posthog releases can emit
    noisy runtime errors even while disabled. This adapter matches the minimal
    Chroma component lifecycle contract and avoids constructing PostHog at all.
    """

    def __init__(self, system: object) -> None:
        self._system = system
        self._dependencies: set[object] = set()
        self._running = False

    def capture(self, event: object) -> None:
        """Drop a product telemetry event."""

    def dependencies(self) -> set[object]:
        """Return component dependencies for Chroma's lifecycle manager."""
        return self._dependencies

    def start(self) -> None:
        """Mark the no-op component as running."""
        self._running = True

    def stop(self) -> None:
        """Mark the no-op component as stopped."""
        self._running = False

    def reset_state(self) -> None:
        """Reset no-op component state."""
        self._running = False
