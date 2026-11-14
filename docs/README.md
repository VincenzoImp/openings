# Openings documentation

Use the dashboard by hand, REST for scripts, or MCP with your own agent. All three
work on the same workspace. New here? Read the [README](../README.md), then
[Getting started](user/getting-started.md).

| I want to... | Read |
|---|---|
| Understand the concepts and the daily loop | [How it works](user/how-it-works.md) |
| Install Openings and make my first application | [Getting started](user/getting-started.md) |
| Review jobs, handle duplicates or set up searches | [Jobs and sources](user/jobs-and-sources.md) |
| Prepare, send and track applications | [Applications](user/applications.md) |
| Fill in my profile, Preferences and templates | [Profile, Preferences and Templates](user/profile-preferences-templates.md) |
| Let an AI agent help, and review what it did | [Work with an agent](user/agents.md) |
| Write scripts | [REST API](user/api.md) |
| Back up, restore, upgrade or open Openings to other devices | [Operations](user/operations.md) |
| Set environment variables | [Configuration](user/configuration.md) |
| Run from source or contribute | [Contributing](../CONTRIBUTING.md) and [Architecture](developer/architecture.md) |
| Report a vulnerability | [Security policy](../SECURITY.md) |
| See what changed | [Changelog](../CHANGELOG.md) |

The running server publishes the reference for every operation at `/api/docs` and
its schema at `/api/openapi.json`; MCP clients read the tools and their inputs from
the server. The pages here do not repeat them.
