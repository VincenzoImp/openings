# Openings compared

Openings is one of several ways to run a job search. This page compares it with
the tools people most often weigh it against, on facts each project publishes.
Every competitor fact links to its source and was checked on **16 November
2026**; projects change, so follow the link before you rely on one. Corrections
are welcome as an issue.

## At a glance

| | Self-hosted | Account | AI inside | Agent via MCP | Collects from company job boards | One-key triage | Auto-apply | License |
|---|---|---|---|---|---|---|---|---|
| **Openings** | Yes: one container, one SQLite file | No; an owner password | None: bring your own agent | The whole workspace | 12 platforms | Yes, every decision undoable | No: nothing in it can submit to an employer | MIT |
| A spreadsheet | Your choice | Your choice | No | No | No | No | No | — |
| Huntr, Teal, Simplify | No: hosted services [^saas] | Yes [^saas] | Yes, on paid plans [^saas] | Not documented | No: a browser extension saves jobs [^saas] | Not documented | Autofill (Huntr, Simplify); Simplify+ "Autopilot" [^saas] | Proprietary |
| Auto-apply bots, such as AIHawk | Runs on your desktop [^aihawk] | An LLM provider account [^aihawk] | Yes [^aihawk] | No [^aihawk] | Not documented | No | **Yes**: fills and submits forms [^aihawk] | MIT [^aihawk] |
| career-ops | Runs in your AI CLI, on local files [^careerops] | No [^careerops] | Your CLI's agent [^careerops] | It is a skill pack for the agent itself [^careerops] | Ashby, Greenhouse, Lever, Wellfound [^careerops] | No: it scores and reports [^careerops] | No: "You press Submit" [^careerops] | MIT [^careerops] |
| job-ops | Yes, Docker Compose; also a paid cloud [^jobops] | Yes: JobOps accounts or SSO [^jobops] | Yes, your provider or key [^jobops] | Not documented | Job boards (LinkedIn, Indeed, Glassdoor and others), not company ATS boards [^jobops] | Not documented | No [^jobops] | Source-available, no commercial hosting [^jobops] |
| JobSync | Yes, Docker with a bundled Postgres [^jobsync] | Yes: a local sign-in [^jobsync] | Yes: an assistant on Ollama or a cloud provider [^jobsync] | Adds jobs and interview questions [^jobsync] | Greenhouse, Lever, Ashby [^jobsync] | Not documented | No [^jobsync] | MIT [^jobsync] |

## How to choose

- **A spreadsheet** costs nothing and does what you make it do. Openings starts to
  pay off when you follow more than a few searches and companies: it collects them
  every day, removes duplicates and keeps every decision.
- **Huntr, Teal and Simplify** are polished hosted trackers with browser
  extensions. They keep your data on their servers and charge for their AI.
  Openings keeps everything in one file on your machine and has no AI of its own.
- **Auto-apply bots** send many applications for you. Openings does the opposite:
  your agent tailors each application, one per job, and you send it yourself.
- **career-ops** and Openings are complementary. career-ops is a skill pack that
  lives in your agent's session, with its files. Openings is the persistent
  workspace: scheduled collection, a database, a dashboard and a REST API that a
  person or any agent can drive.
- **job-ops** searches many job boards and has a hosted plan, with built-in AI.
  **JobSync** is a self-hosted tracker with a built-in assistant, interview tools
  and Greenhouse, Lever and Ashby collection, on Postgres with a local account.
  Openings needs no database server and no account, and gives your own agent the
  whole workspace over MCP.

What Openings does not do: it has one user, no hosted version, no browser
extension, no reply detection from your mailbox and no auto-apply.

## Openings, in its own docs

- Collection: LinkedIn, Indeed and Glassdoor searches, company careers pages on
  12 platforms, the Hacker News "Who is hiring?" thread and RSS
  ([Jobs and sources](user/jobs-and-sources.md#sources)).
- Triage: one key to shortlist or dismiss, every decision undoable
  ([Jobs and sources](user/jobs-and-sources.md#review-jobs)).
- Agents and what they can do ([Work with an agent](user/agents.md#security-model)).
- One container, one SQLite file, daily backups ([Operations](user/operations.md#backups)).

## Sources

All checked on 16 November 2026.

[^saas]: Teal, [Teal vs Huntr](https://www.tealhq.com/post/teal-vs-huntr) and [Teal vs Simplify](https://www.tealhq.com/post/teal-vs-simplify); [Best job tracking app 2026](https://jobshinobi.com/compare/best-job-tracking-app-2026); [Teal vs Huntr vs Simplify](https://bestjobsearchapps.com/articles/en/teal-vs-huntr-vs-simplify-pros-and-cons). Third-party comparisons; plans and prices change often.
[^aihawk]: [feder-cr/Jobs_Applier_AI_Agent README](https://github.com/feder-cr/Jobs_Applier_AI_Agent).
[^careerops]: [career-ops-hq/career-ops README](https://github.com/career-ops-hq/career-ops): "Human-in-the-Loop", "Portal Scanner" and the `apply` mode.
[^jobops]: [DaKheera47/job-ops README](https://github.com/DaKheera47/job-ops): "What is JobOps?", "Supported Job Boards", "AI Providers", "Cloud" and "License".
[^jobsync]: [Gsync/jobsync README](https://github.com/Gsync/jobsync): quick start (create your account), `DATABASE_URL` (bundled Postgres), automated discovery (Greenhouse, Lever, Ashby), "MCP Server (AI Agent Integration)" and the AI settings.
