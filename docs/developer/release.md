# Release process

Images are published from Git tags.

## Before tagging

```bash
uv run pre-commit run --all-files
uv run mypy src/openings
uv run pytest --cov=openings --cov-fail-under=60
npm --prefix frontend run quality
docker compose config
sh docker/smoke.sh
```

Check that `pyproject.toml`, `CHANGELOG.md` and the docs agree on the version.
Move the `Unreleased` notes under the new heading with the date.

## Tag

```bash
git tag -a v1.2.0 -m "Openings 1.2.0"
git push origin v1.2.0
```

## Publish

`.github/workflows/publish-release.yml` runs on `v*` tags: multi-arch build
(`linux/amd64`, `linux/arm64`), SBOM and provenance, pushed to Docker Hub as
`<semver>`, `<major>.<minor>`, `<major>`, `latest` and `sha-<commit>`. The
image name is `vincenzoimp/openings`, overridable through the repository
variable `DOCKERHUB_IMAGE`.

## Scope

A release changes runtime behaviour, packaging, Docker deployment, docs and
verification together. Planning notes and generated state stay out of the
repository.
