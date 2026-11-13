"""Replace a name wherever the discovery package looks it up."""

from openings.discovery import feeds, models, network, resolution, runs, service, sources, tasks

MODULES = (models, network, feeds, resolution, sources, runs, tasks, service)


def patch_discovery(monkeypatch, name, value):
    """Patch ``name`` in every discovery module that uses it, as if it were one module."""
    found = [module for module in MODULES if name in vars(module)]
    assert found, f"No discovery module uses {name}."
    for module in found:
        monkeypatch.setattr(module, name, value)
