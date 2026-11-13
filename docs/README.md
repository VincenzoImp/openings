# Openings documentation

Use the dashboard by hand, REST for scripts, or MCP with your external agent. All
three work with the same jobs, career knowledge, documents and collection settings.

| I want to… | Guide |
|---|---|
| Install Openings and add a first job | [Setup and first use](user/getting-started.md) |
| Search portals or follow chosen companies | [Collection](user/sources.md) |
| Organize experience, skills and reusable wording | [Career entries and claims](user/career.md) |
| State my rules for jobs and documents, and the facts employers ask about | [Policy](user/policy.md) |
| Prepare a CV, letter or form answers | [Application documents](user/applications.md) |
| Plan deadlines, priorities and employer requirements | [Plan and track requirements](user/applications.md#plan-and-track-requirements) |
| Close, reopen or delete several applications, or merge repeated vacancies | [Keep, dismiss or delete](user/applications.md#keep-dismiss-or-delete) |
| Let an AI agent run and improve my search | [Agent-operated job search](user/agent-operated.md) |
| Connect an AI agent | [Agents and MCP](user/agents.md) |
| Give an agent a ready workspace with the operating mandate | [Operator workspace template](../examples/operator-workspace/README.md) |
| Read the workflow skills agents follow | [Skills](../skills/) |
| Write scripts | [REST API](user/api.md) |
| Move, restore, upgrade or operate a workspace | [Operations](user/operations.md) |
| Set the server's environment variables | [Configuration](user/configuration.md) |
| Run from source or contribute | [Contributing](../CONTRIBUTING.md) and [Architecture](developer/architecture.md) |
| Report a vulnerability | [Security policy](../SECURITY.md) |
| See what changed in each release | [Changelog](../CHANGELOG.md) |

The running server publishes REST reference at `/api/docs` and schemas at
`/api/openapi.json`. MCP clients discover the corresponding tools and inputs.
Authenticated `/api/v1/capabilities` maps operations to all three interfaces.
