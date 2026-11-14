# Maintaining

Notes for the maintainer: releases and repository settings.

## Release

Check that the latest run of the weekly workflow (`weekly.yml`) on `main` passed.
Rename `## Unreleased` in [CHANGELOG.md](../../CHANGELOG.md) to `## X.Y.Z — date`,
set every version at once and check the locks:

```bash
python3 scripts/bump_version.py X.Y.Z && uv lock --check
npm --prefix frontend install --package-lock-only --ignore-scripts
```

Merge that change, then tag `vX.Y.Z` on `main`. The release workflow
(`images.yml`) waits for the CI run of the tagged commit and requires it to pass,
audits the dependencies, builds both images, smoke-tests each pushed digest
(`scripts/smoke_image.sh`), publishes `vincenzoimp/openings:X.Y.Z` and `X.Y`, and
creates the GitHub Release from the changelog section.

A release that changes the schema ships its migration. Once it is tagged, write
the fixture the next migration upgrades from:

```bash
uv run python scripts/release_fixture.py --tag vX.Y.Z
```

It writes `backend/tests/fixtures/workspace-<schema>.sql.gz` from that tag's own
synthetic seed.

## Dependencies

Dependabot proposes updates weekly. Two are made by hand:

- **Playwright:** `@playwright/test` and the Playwright image in `ci.yml`,
  `weekly.yml` and `screenshots.yml` move together; CI checks that they match.
- **Python minor version:** the runtime image, CI and `requires-python` move
  together once every compiled dependency publishes wheels for it.

## Repository settings

`main` is protected by a ruleset: pull requests only, required checks `backend`,
`frontend`, `e2e` and `container (amd64)` passing on a branch up to date with
`main`, no force-push, deletion or bypass; no review is required. A change that
renames those jobs updates the ruleset (`gh api repos/VincenzoImp/openings/rulesets`).
