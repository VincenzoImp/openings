"""Discovery helpers: patch a name in every module, open a provider gate, script DNS."""

import ipaddress
import socket

import httpx

from openings.collectors.policy import ProviderPatch
from openings.discovery import feeds, models, network, resolution, runs, service, sources, tasks

MODULES = (models, network, feeds, resolution, sources, runs, tasks, service)
CLIENT = httpx.Client


def patch_discovery(monkeypatch, name, value):
    """Patch ``name`` in every discovery module that uses it, as if it were one module."""
    found = [module for module in MODULES if name in vars(module)]
    assert found, f"No discovery module uses {name}."
    for module in found:
        monkeypatch.setattr(module, name, value)


def mock_http(monkeypatch, send):
    """Answer every request of an httpx client with ``send(request)``; the gate still applies."""
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: CLIENT(**{**kwargs, "transport": httpx.MockTransport(send)}),
    )


def open_gate(service, *providers):
    """Let ``providers`` send requests without the minimum interval between them."""
    for provider in providers:
        current = service.providers.get(provider)["version"]
        service.update_provider(
            provider, ProviderPatch(expected_version=current, min_interval_seconds=0)
        )


def synthetic_resolver(monkeypatch, answers):
    """Return the next scripted address for each lookup of a host; names never reach DNS."""
    calls = []

    def resolve(host, port, *args, **kwargs):
        if host in answers:
            calls.append(host)
            address = answers[host].pop(0)
        else:
            address = str(ipaddress.ip_address(host))  # the pinned dial itself
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (address, port))]

    monkeypatch.setattr(network.socket, "getaddrinfo", resolve)
    return calls
