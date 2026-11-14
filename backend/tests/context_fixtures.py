"""A realistic synthetic workspace for the start read: what an owner has after a few months."""

from openings.actors import OWNER, acting_as
from openings.career import ClaimCreate, KnowledgeCreate, ProfileUpdate, TemplateCreate

NARRATIVE = (
    "Led the design of a service that ingests partner data, validates it and publishes it to "
    "internal consumers. Worked with product and operations on rollout plans, wrote the runbooks "
    "and mentored two engineers. Reduced the time to onboard a partner from weeks to days, and "
    "kept the error budget through two peak seasons. "
)
TEX = "\\documentclass{article}\n\\begin{document}\n" + "\\section{Synthetic}\nText.\n" * 120


def realistic(app, entries=18, jobs=60):
    """Profile, five Preferences sections, career entries with highlights, two templates,
    jobs in every triage state and a few applications."""
    workspace, career, preferences = app.state.workspace, app.state.career, app.state.preferences
    with acting_as(OWNER):
        profile = career.get_profile()
        career.update_profile(
            ProfileUpdate(
                expected_version=profile["version"],
                name="Alex Example",
                headline="Senior backend engineer",
                location="Zurich, Switzerland",
                email="alex@example.org",
                summary="Backend engineer building data platforms. " * 6,
                links=[{"label": "GitHub", "url": "https://github.com/example"}],
            )
        )
        statements = {
            "looking_for": ["Senior backend or platform roles.", "Zurich, Basel or remote."] * 3,
            "ruled_out": ["No defence or gambling.", "No roles below senior."] * 3,
            "facts": ["EU citizen with a Swiss B permit.", "Notice period: three months."] * 3,
            "writing": ["At most two pages.", "No buzzwords such as passionate."] * 3,
            "working_with_me": ["Ask before preparing anything in French."] * 4,
        }
        for section, texts in statements.items():
            items = [{"text": text} for text in texts]
            if section == "writing":
                items = [{**item, "scope": "cv"} for item in items]
            preferences.update_preferences(section, {"expected_version": 0, "items": items})
        for index in range(entries):
            entry = career.create_knowledge(
                KnowledgeCreate(
                    kind="experience" if index % 3 else "project",
                    title=f"Synthetic role {index}",
                    organization=f"Example Org {index}",
                    dates={"kind": "period", "start": f"{2010 + index % 12}-03", "end": "2024-06"},
                    narrative=NARRATIVE * 3,
                )
            )
            for number in range(3):
                career.create_claim(
                    ClaimCreate(
                        career_id=entry["id"],
                        text=f"Synthetic highlight {number} of role {index}: cut latency by 20%.",
                        approved=number < 2,
                    )
                )
        for kind in ("cv", "letter"):
            career.create_template(
                TemplateCreate(
                    name=f"Synthetic {kind}",
                    kind=kind,
                    tex=TEX,
                    guidance="Concise, evidence first. " * 20,
                    rules={"max_pages": 2},
                )
            )
        created = [
            workspace.ingest_job(
                {"title": f"Engineer {n}", "company": f"Company {n}", "posting": "Build. " * 50}
            )
            for n in range(jobs)
        ]
        for job in created[: jobs // 3]:
            workspace.set_triage(job["id"], "dismissed", job["version"], "Too junior.")
        for job in created[jobs // 3 : jobs // 3 + 6]:
            workspace.set_triage(job["id"], "shortlisted", job["version"])
    return created
