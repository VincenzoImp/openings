# Release Process

The project publishes Docker images from Git tags.

## Before Tagging

Run:

```bash
uv run pytest
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
uv run pre-commit run --all-files
uv run mypy src/job_search_tool --ignore-missing-imports
docker build -t job-search-tool:release .
docker compose config
```

Also verify that `CHANGELOG.md`, `pyproject.toml`, and release docs agree on the
intended version.

## Docker Publishing

`.github/workflows/publish-release.yml` runs when a `v*` tag is pushed. It
builds multi-arch images for Docker Hub and publishes:

- full semver tag,
- major/minor tag,
- major tag,
- `latest`,
- SHA tag,
- SBOM,
- provenance.

The default image name is `vincenzoimp/job-search-tool`, overridable through the
repository variable `DOCKERHUB_IMAGE`.

## Release PR Scope

Release PRs should keep runtime behavior, packaging, Docker deployment, docs,
and verification aligned. Avoid carrying internal planning artifacts or
generated runtime state in release branches.
