## Why

<!-- The problem or workflow this change addresses. Link issues with "Fixes #123". -->

## What

<!-- The main changes, including any REST, MCP, schema or dashboard behavior. -->

## Checks

- [ ] I ran the checks in CONTRIBUTING.md › Check a change, and the browser tests for a dashboard change
- [ ] Business logic stays in shared services; every dashboard action is a REST operation, and every operation that is not owner-only is an MCP tool or names one (`mcp=`)
- [ ] Versioned updates, immutable document revisions, exact file ownership and deletion rules still hold
- [ ] A schema change edits the unreleased migration and its tests, and the CHANGELOG says what it means for upgrade and restore
- [ ] Tests, fixtures, examples and screenshots use synthetic data only
- [ ] User docs, skills and CHANGELOG (Unreleased) follow any change of behavior

## Screens

<!-- For a dashboard change: images of every changed screen, desktop and mobile, light and dark, from the Screenshots workflow's artifact or `npm --prefix frontend run screenshots`. Delete this section otherwise. -->
