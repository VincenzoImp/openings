# Working on Openings

Read README.md, CONTRIBUTING.md and docs/developer/architecture.md before changing
behavior. The running OpenAPI schema and MCP tools describe the current contract;
backend/openings/operation-inventory.json maps logical operations across interfaces.

- Keep business logic in shared services. Dashboard, REST and MCP must expose the
  same useful operations, allowing documented authentication/transport differences.
- Preserve version checks, context/document immutability, exact file ownership,
  reversible dismissal and deliberate permanent deletion.
- Keep incomplete automatic candidates in collection checkpoints; admit usable
  posting text before archive and count bookkeeping. Preserve manual partial input.
- Enforce one non-Closed application per job in shared services and SQLite.
  Starting an application shortlists its job; document work never submits it.
- Keep SQLite portable and the core independent of model, browser and TeX runtimes.
  Generation and compilation belong to an external agent.
- Provider requests must use the shared persisted gate, including previews,
  redirects and manual runs. Never bypass it with an unguarded HTTP client.
- Ship English code/UI/docs and synthetic public fixtures. Keep databases,
  credentials, personal documents and machine-specific deployment files out of Git.
- Use focused invariant tests and practical complete workflows after meaningful
  changes. Check populated desktop/mobile views for dashboard changes.
- Prefer small, clear services and coherent commits. Parallel work should use
  isolated worktrees and explicit file ownership; remove temporary work afterward.

Do not merge, publish artifacts or deploy an installation unless the current task
explicitly authorizes that action. Keep release-specific work notes outside the
public product tree.
