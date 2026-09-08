# Security

Openings is a self-hosted tool that holds personal data: postings you looked
at, applications you made, CVs and cover letters. It binds to `127.0.0.1` by
default and every surface (dashboard, `/api`, `/mcp`) can change that data, so
set `OPENINGS_API_TOKEN` before exposing the port to any network you do not
control, and never expose it to the internet.

To report a vulnerability, open a GitHub issue with the label `security` or
contact the maintainer through the profile on GitHub. Please do not include
your own database or attachments in the report.
