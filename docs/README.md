# Openings documentation

Use the dashboard by hand, REST for scripts, or MCP with your external agent. All
three work with the same jobs, career knowledge, documents and collection settings.

| I want to… | Guide |
|---|---|
| Install Openings and add a first job | [Setup and first use](user/getting-started.md) |
| Search portals or follow chosen companies | [Collection](user/sources.md) |
| Organize experience, skills and reusable wording | [Career entries and claims](user/career.md) |
| Prepare a CV, letter or form answers | [Application documents](user/applications.md) |
| Connect an AI agent | [Agents and MCP](user/agents.md) |
| Classify job fit | [Optional scoring](user/scoring.md) |
| Write scripts | [REST API](user/api.md) |
| Move, restore or operate a workspace | [Operations](user/operations.md) |
| Run from source or contribute | [Contributing](../CONTRIBUTING.md) and [Architecture](developer/architecture.md) |

The running server publishes REST reference at `/api/docs` and schemas at
`/api/openapi.json`. MCP clients discover the corresponding tools and inputs.
Authenticated `/api/v1/capabilities` maps operations to all three interfaces.
