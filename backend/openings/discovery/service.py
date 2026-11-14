"""DiscoveryService: the shared provider gate, composed with sources, runs and tasks."""

from __future__ import annotations

from ..collectors.policy import ProviderBudget, ProviderStore, provider_for_url
from .network import MAX_FEED_BYTES, fetch_bytes, public_addresses, public_url
from .runs import RunOperations
from .sources import SourceOperations
from .tasks import TaskOperations


class DiscoveryService(SourceOperations, RunOperations, TaskOperations):
    def __init__(self, workspace):
        self.workspace = workspace
        self.db = workspace.db
        self.providers = ProviderStore(self.db)

    def http_budget(self, provider_id, active=None):
        """Shared per-request gate for collectors, previews and manual URL import."""
        return ProviderBudget(
            self.providers,
            provider_id,
            active=active,
            validate_url=public_url,
            resolve_host=public_addresses,
        )

    provider_for_url = staticmethod(provider_for_url)

    def fetch_bytes(
        self,
        url,
        *,
        provider_id="manual",
        maximum=MAX_FEED_BYTES,
        budget=None,
        method="GET",
        body=None,
    ):
        if provider_id == "manual":
            provider_id = provider_for_url(url)
        return fetch_bytes(
            url,
            maximum=maximum,
            budget=budget or self.http_budget(provider_id),
            method=method,
            body=body,
        )
