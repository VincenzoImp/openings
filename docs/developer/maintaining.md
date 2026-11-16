# Maintaining

Notes for the maintainer: releases, the demo reel and repository settings.

## Release

Check that the latest run of the weekly workflow (`weekly.yml`) on `main` passed.
Rename `## Unreleased` in [CHANGELOG.md](../../CHANGELOG.md) to `## X.Y.Z — date`,
set every version at once and check the locks:

```bash
python3 scripts/bump_version.py X.Y.Z && uv lock --check
npm --prefix frontend install --package-lock-only --ignore-scripts
```

The section starts with its **headline**: one plain line of at most 100 characters,
before any list or bold heading, such as `Workday roles with several locations stay
listed`. The release is titled `Openings X.Y.Z: <headline>`, and the rest of the
section, with a fixed upgrade line, is its notes. The release workflow fails before
building anything if the section or its headline is missing.

Merge that change, then tag `vX.Y.Z` on `main`. The release workflow
(`images.yml`) waits for the CI run of the tagged commit and requires it to pass,
audits the dependencies, builds both images, smoke-tests each pushed digest
(`scripts/smoke_image.sh`, including the OCI labels), and publishes one multi-arch
index tagged `X.Y.Z` and `X.Y` on Docker Hub (`vincenzoimp/openings`) and on the
GHCR mirror (`ghcr.io/vincenzoimp/openings`), with the same digest on both. A final
release also moves `latest`, unless a newer final release exists, and smoke-tests
`latest` as pulled. A prerelease (`X.Y.Z-rc.1`) moves neither `X.Y` nor `latest`.
Then it creates the GitHub Release.

To point `latest` at an already published release without a local login, run the
`latest.yml` workflow: `gh workflow run latest.yml -f version=X.Y.Z`. It checks that
both architectures are there, moves `latest` on Docker Hub (and on GHCR when that
version is mirrored), compares the digests and checks that `latest` reports the
version on `/health`.

A release that changes the schema ships its migration. Once it is tagged, write
the fixture the next migration upgrades from:

```bash
uv run python scripts/release_fixture.py --tag vX.Y.Z
```

It writes `backend/tests/fixtures/workspace-<schema>.sql.gz` from that tag's own
synthetic seed.

### Cadence

- In launch week, at most one release a day; afterwards at most one a week,
  unless a bug blocks a user. Batch the rest in the next release.
- 0.28.0 may change the schema once, as a single migration verified on a copy of
  the maintainer's own workspace. No 0.28.x release changes the schema.
- The next schema change is 1.0.0, which tests chained upgrades from 0.28.

## Traffic archive

GitHub keeps traffic for 14 days only. `scripts/traffic_archive.py` appends one
dated JSON line a day (views, clones, referrers, popular paths, stars, forks,
issues by author and the Docker Hub pull count with its daily change) to a file
outside the checkout; a second run on the same day writes nothing. It addresses
the repository by its numeric id and reads the token from `GITHUB_TOKEN`,
`GH_TOKEN` or `gh auth token`, without writing it. Run it daily from cron:

```bash
15 6 * * * cd /path/to/openings && python3 scripts/traffic_archive.py --output "$HOME/openings-traffic/traffic.jsonl"
```

Never commit its output.

## Demo reel

`npm --prefix frontend run reel` (and `-- --dark`) builds the dashboard, records
about 20 seconds of it on the demo workspace (`frontend/tests/reel.spec.ts`, its
own Playwright project, never run in CI) and encodes `docs/images/demo.gif` and
`demo-dark.gif` with ffmpeg, which must be on `PATH`. It fails when a GIF is over
5 MB. Everything on screen is the dashboard except the cursor, the key chips, the
captions and the end card. The reel keeps its own clock, so two runs differ only in
encoder noise. `frontend/reel/` (ignored by Git) receives the MP4 master and the
track the video is cut from: each scene's caption and focal regions, the cursor,
the clicks and the keys. Re-render both after a change to a screen it shows.

The `video` Playwright project (`frontend/tests/video.spec.ts`) records the same
kind of track and the bare frames, at twice the pixels, from a running
`openings demo` that an agent works on at the same time: before the agent, live
while it works, and after. A capture script outside the repository starts the
demo and the agent session and sets its variables (see the spec's header); the
recorder both specs share is `frontend/tests/reel.ts`.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../images/demo-dark.gif">
  <img alt="The demo reel: sources, Jobs › New, the agent's dismissals, a Ready application, Mark applied and Today" src="../images/demo.gif">
</picture>

## Dependencies

Dependabot proposes updates weekly, each version at least seven days old
(`cooldown`). Two are made by hand:

- **Playwright:** `@playwright/test` and the Playwright image in `ci.yml`,
  `weekly.yml` and `screenshots.yml` move together; CI checks that they match.
- **Python minor version:** the runtime image, CI and `requires-python` move
  together once every compiled dependency publishes wheels for it.

## Static analysis

`codeql.yml` analyses the Python and TypeScript on pull requests, on `main` and
weekly; its findings are code scanning alerts. `zizmor.yml` audits the workflows
and the Dependabot configuration on every change under `.github/` and fails on
any finding. Neither is a required check. Pin every action by commit SHA with
its version in a comment.

## Repository settings

`main` is protected by a ruleset: pull requests only, required checks `backend`,
`frontend`, `e2e` and `container (amd64)` passing on a branch up to date with
`main`, no force-push, deletion or bypass; no review is required. A change that
renames those jobs updates the ruleset (`gh api repos/VincenzoImp/openings-job-search/rulesets`).

The project description is the same in `pyproject.toml`, the Dockerfile label,
the `images.yml` index annotation and `frontend/index.html`;
`scripts/check_package.py` fails when one differs. Keep the GitHub About text
equal to it.

The `ghcr.io/vincenzoimp/openings` package is public. The release jobs push to
Docker Hub with the `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` secrets and to GHCR
with the workflow's own token (`packages: write` on the publishing jobs only).
The Docker Hub overview is edited by hand from `docs/dockerhub.md`; set the
repository variable `DOCKERHUB_DESCRIPTION_SYNC` to `true` and add a Read, Write,
Delete token as `DOCKERHUB_DESCRIPTION_TOKEN` to sync it on every final release.
