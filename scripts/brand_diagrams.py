"""Draw the README diagrams in both themes from the dashboard's tokens.

Usage:
    uv run python scripts/brand_diagrams.py

Writes docs/images/flow.svg, agent-vs-you.svg and funnel.svg, each with a
`-dark` twin. Colours come from `frontend/src/ui/tokens.css` (scripts/brand_tokens.py),
type is Inter at 400 to 600 from the dashboard's own font package, embedded so
github.com draws it without the font installed (`npm ci` in frontend/ first). Every
diagram is 1200 wide and no text is under 14 px.

The funnel is example data, never anyone's results: its counts are read from a new
demo workspace (openings.demo), seeded in a temporary directory.
"""

import base64
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens

ROOT = brand_tokens.ROOT
IMAGES = ROOT / "docs" / "images"
FONT = ROOT / "frontend/node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2"
WIDTH = 1200
MIN_TEXT = 14
REGULAR, MEDIUM, SEMIBOLD = 400, 500, 600


class Drawing:
    """An SVG of the given height whose colours are token names, resolved per theme."""

    def __init__(self, height, label, palette):
        self.height, self.label, self.palette, self.parts = height, label, palette, []

    def colour(self, token):
        return "none" if token is None else self.palette[token]

    def rect(self, x, y, w, h, fill=None, stroke=None, radius=8, width=1.5, dash=None):
        dashed = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
            f'fill="{self.colour(fill)}" stroke="{self.colour(stroke)}" '
            f'stroke-width="{width if stroke else 0}"{dashed}/>'
        )

    def path(self, d, stroke=None, fill=None, width=1.75):
        self.parts.append(
            f'<path d="{d}" fill="{self.colour(fill)}" stroke="{self.colour(stroke)}" '
            f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    def text(self, x, y, value, size=15, weight=REGULAR, colour="text", anchor="start", lead=None):
        """One line, or several (a list) ``lead`` apart."""
        assert size >= MIN_TEXT, value
        lines = [value] if isinstance(value, str) else value
        lead = lead or round(size * 1.45)
        track = ' letter-spacing="-0.4"' if size >= 22 else ""
        for index, line in enumerate(lines):
            self.parts.append(
                f'<text x="{x}" y="{y + index * lead}" font-size="{size}" '
                f'font-weight="{weight}" fill="{self.colour(colour)}" '
                f'text-anchor="{anchor}"{track}>{escape(line)}</text>'
            )

    def arrow(self, x1, x2, y, colour="text-3"):
        self.path(f"M{x1} {y}H{x2}M{x2 - 7} {y - 6}L{x2} {y}L{x2 - 7} {y + 6}", stroke=colour)

    def check(self, x, y, colour="accent"):
        self.path(f"M{x} {y}l5 5l10 -11", stroke=colour, width=2.25)

    def dot(self, x, y, colour="text"):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{self.colour(colour)}"/>')

    def svg(self, font):
        style = (
            '@font-face{font-family:"Inter";font-style:normal;font-weight:400 600;'
            f'src:url(data:font/woff2;base64,{font}) format("woff2")}}'
            'text{font-family:"Inter",ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif}'
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {self.height}" '
            f'width="{WIDTH}" height="{self.height}" role="img" aria-label="{escape(self.label)}">\n'
            f"<style>{style}</style>\n" + "\n".join(self.parts) + "\n</svg>\n"
        )


# The four steps of a day: who acts, the step, a caption and the body. Only the
# agent's step is in the accent; your own last step is filled.
STEPS = (
    (
        "You, once",
        "You set it up",
        "in your own words",
        [
            "Profile: your career",
            "Preferences: your rules",
            "Templates: CV and letter",
            "Sources: what you watch",
        ],
    ),
    (
        "Openings",
        "Fresh jobs",
        "on each source's schedule",
        [
            "LinkedIn, Indeed, Glassdoor,",
            "12 hiring platforms, HN,",
            "RSS and job links.",
            "Repeats are left out.",
        ],
    ),
    (
        "Your agent, over MCP",
        "Your agent decides and prepares",
        "Claude Code, Codex, any client",
        [
            "Reads each job by your rules,",
            "dismisses with a reason,",
            "writes the CV and letter",
            "as PDFs, and ranks them.",
        ],
    ),
    (
        "You",
        "You apply, best first",
        "on the employer's site",
        [
            "Ready is ranked by priority,",
            "then deadline. Openings",
            "tracks the replies and",
            "follow-ups.",
        ],
    ),
)
COLUMN, GAP = 260, 40


def flow(palette):
    d = Drawing(
        500,
        "You set it up once: Profile, Preferences, Templates and Sources. Openings brings in "
        "fresh jobs, with repeats left out. Your agent decides and prepares over MCP: it reads "
        "each job by your rules, dismisses with a reason, writes the CV and letter as PDFs and "
        "ranks them. You apply, best first, on the employer's site. Every step works by hand, "
        "over REST or over MCP. Nothing in Openings can submit an application to an employer.",
        palette,
    )
    for index, (who, title, caption, body) in enumerate(STEPS):
        x = 20 + index * (COLUMN + GAP)
        agent, last = index == 2, index == 3
        ink = "accent-text" if agent else "text-2"
        d.text(x + COLUMN / 2, 40, who, size=16, weight=MEDIUM, colour=ink, anchor="middle")
        d.path(
            f"M{x} 66V58H{x + COLUMN}V66", stroke="accent" if agent else "border-strong", width=1.5
        )
        if agent:
            d.rect(x, 92, COLUMN, 120, fill="accent-soft", stroke="accent", radius=12)
        elif last:
            d.rect(x, 92, COLUMN, 120, fill="primary", radius=12)
        else:
            d.rect(x, 92, COLUMN, 120, fill="surface", stroke="border-strong", radius=12)
        sub = "on-primary" if last else "text-2"
        heading = "on-primary" if last else "text"
        d.text(x + 20, 122, str(index + 1), size=14, weight=MEDIUM, colour=sub)
        lines = (
            [title]
            if len(title) < 22
            else title.rsplit(" ", 2)[0:1] + [" ".join(title.split()[-2:])]
        )
        d.text(
            x + 20,
            150 if len(lines) == 1 else 146,
            lines,
            size=20,
            weight=SEMIBOLD,
            colour=heading,
            lead=24,
        )
        d.text(x + 20, 196, caption, size=14, weight=MEDIUM, colour=sub)
        d.text(x + 20, 246, body, size=15, colour="text-2", lead=22)
        if index < 3:
            d.arrow(x + COLUMN + 6, x + COLUMN + GAP - 6, 152)
    d.path(f"M20 336V346H{WIDTH - 20}V336", stroke="border-strong", width=1.5)
    d.text(WIDTH / 2, 378, "By hand · REST · MCP", size=18, weight=SEMIBOLD, anchor="middle")
    d.text(
        WIDTH / 2,
        404,
        "Every step works by hand in the dashboard, from scripts over REST, or through your agent over MCP.",
        size=15,
        colour="text-2",
        anchor="middle",
    )
    d.path(f"M20 436H{WIDTH - 20}", stroke="border", width=1)
    d.rect(22, 460, 16, 16, fill="primary", radius=4)
    d.text(
        50,
        473,
        "Nothing in Openings can submit an application to an employer or contact one.",
        size=15,
        colour="text-2",
    )
    return d


HOLDS = (
    ("Your career", ["experience and highlights;", "★ always in your CV"]),
    ("Your rules", ["Preferences, in your", "own words"]),
    ("Your templates", ["your own TeX, its Limits,", "a default per kind"]),
    ("Your sources", ["the searches and companies", "you watch"]),
)
AGENT = (
    (
        "Decides with reasons",
        ["reads Jobs › New by your Preferences,", "with a reason for every dismissal"],
    ),
    (
        "Writes and compiles",
        ["the tailored CV and letter from your", "templates, as PDFs, until it is Ready"],
    ),
    (
        "Ranks what is Ready",
        ["a priority, a deadline and a salary", "range with its basis"],
    ),
    ("Briefs you before an interview", ["and records the replies you tell it"]),
    (
        "Reports back",
        ["what is Ready and what needs you;", "Openings attributes every write"],
    ),
)
YOU = (
    ("Set it up once", ["Profile, Preferences, Templates", "and Sources"]),
    ("Approve and correct", ["highlights, dismissals and", "what your agent may do alone"]),
    ("Apply on the employer's site", ["best first, with everything", "prepared"]),
    ("Own the data", ["one SQLite file on your machine,", "with daily verified backups"]),
)


def column(d, x, y, items, mark):
    for title, body in items:
        mark(x + 2, y - 6)
        d.text(x + 32, y, title, size=17, weight=MEDIUM)
        d.text(x + 32, y + 25, body, size=15, colour="text-2", lead=22)
        y += 38 + 22 * len(body)


def agent_vs_you(palette):
    d = Drawing(
        694,
        "What Openings holds: your career, rules, templates and sources. What your agent does "
        "over MCP: decides with reasons, writes and compiles the CV and letter, ranks what is "
        "Ready, briefs you before an interview and reports back. What stays yours: set it up "
        "once, approve and correct, apply on the employer's site, own the data. Nothing in "
        "Openings can submit an application to an employer.",
        palette,
    )
    d.rect(20, 20, 300, 530, fill="bg-subtle", stroke="border-strong", radius=12)
    d.text(44, 66, "What Openings holds", size=22, weight=SEMIBOLD)
    d.text(44, 94, "your career, rules, templates", size=15, weight=MEDIUM, colour="text-2")
    d.text(44, 116, "and sources", size=15, weight=MEDIUM, colour="text-2")
    column(d, 42, 166, HOLDS, lambda x, y: d.rect(x, y - 7, 12, 12, fill="text-3", radius=3))
    d.rect(340, 20, 460, 530, fill="accent-soft", stroke="accent", radius=12)
    d.text(364, 66, "Your agent, over MCP", size=22, weight=SEMIBOLD)
    d.text(
        364,
        94,
        "Claude Code, Codex or any MCP client.",
        size=15,
        weight=MEDIUM,
        colour="accent-text",
    )
    d.text(364, 116, "No AI runs inside Openings.", size=15, weight=MEDIUM, colour="accent-text")
    column(d, 362, 166, AGENT, lambda x, y: d.check(x, y, "accent"))
    d.rect(820, 20, 360, 530, fill="surface", stroke="text", radius=12)
    d.text(844, 66, "You", size=22, weight=SEMIBOLD)
    d.text(844, 94, "The part worth your time.", size=15, colour="text-2")
    d.text(844, 116, "Every step works by hand too.", size=15, colour="text-2")
    column(d, 842, 166, YOU, lambda x, y: d.dot(x + 4, y, "text"))
    d.rect(20, 574, WIDTH - 40, 100, fill="bg-subtle", stroke="border", radius=12)
    d.text(
        52,
        610,
        "Nothing in Openings can submit to an employer.",
        size=18,
        weight=SEMIBOLD,
    )
    d.text(
        52,
        638,
        [
            "No operation sends anything to an employer, whether you or your agent calls it.",
            "Non-destructive changes can be undone, and permanent deletes happen only when you ask.",
        ],
        size=15,
        colour="text-2",
        lead=22,
    )
    return d


FUNNEL = (
    ("collected", "Jobs collected", "fresh and deduplicated, from four sources"),
    ("shortlisted", "Shortlisted", "kept by fit, by the agent or by hand"),
    ("ready", "Prepared to Ready", "a tailored CV and letter, ranked by priority and deadline"),
    ("sent", "Applied", "by the person, on the employer's site"),
    ("replied", "Replies", "an answer from the employer: an interview, an offer or a no"),
)


def funnel_counts():
    """The funnel of a new demo workspace: each stage counts what reached it."""
    from fastapi.testclient import TestClient

    from openings.app import create_app
    from openings.demo import seed_demo

    with tempfile.TemporaryDirectory() as directory:
        app = create_app(Path(directory) / "demo.sqlite", start_worker=False)
        with TestClient(app):
            seed_demo(app)
            workspace = app.state.workspace
            jobs = workspace.db.one("SELECT count(*) AS n FROM jobs")["n"]
            shortlisted = workspace.db.one("SELECT count(DISTINCT job_id) AS n FROM applications")[
                "n"
            ]
            ready = workspace.list_applications(limit=1)["stage_counts"]["ready"]
            stats = app.state.stats.stats({"period": "all"})
    return {
        "collected": jobs,
        "shortlisted": shortlisted,
        "ready": ready + stats["applied"],
        "sent": stats["applied"],
        "replied": stats["replied"],
    }


def funnel(palette, counts):
    d = Drawing(
        560,
        "Example data: the funnel of the synthetic demo workspace, one fictional person's "
        "job search. "
        + ", ".join(f"{label} {counts[key]}" for key, label, _ in FUNNEL)
        + ". It shows how the funnel reads, not anyone's results.",
        palette,
    )
    d.rect(40, 30, 128, 30, fill="warning-soft", stroke="warning", radius=15, width=1)
    d.text(104, 51, "Example data", size=14, weight=SEMIBOLD, colour="warning", anchor="middle")
    d.text(40, 104, "How the funnel reads", size=26, weight=SEMIBOLD)
    d.text(
        40,
        134,
        "The demo workspace: one fictional person's job search. Not anyone's results.",
        size=15,
        colour="text-2",
    )
    top, full = counts["collected"], 640
    for index, (key, label, caption) in enumerate(FUNNEL):
        y = 180 + index * 64
        d.text(40, y + 18, label, size=17, weight=MEDIUM)
        d.text(40, y + 42, caption, size=14, colour="text-3")
        width = max(8, round(full * counts[key] / top))
        d.rect(500, y, width, 44, fill="accent", radius=6)
        d.text(500 + width + 14, y + 28, str(counts[key]), size=18, weight=SEMIBOLD)
    d.path(f"M40 512H{WIDTH - 40}", stroke="border", width=1)
    d.text(
        40,
        540,
        "Counts read from the demo workspace that docker run … demo opens. Yours depend on "
        "your sources, your Preferences and your agent.",
        size=14,
        colour="text-3",
    )
    return d


def main():
    if not FONT.exists():
        print("Inter is missing: run `npm ci` in frontend/ first.")
        return 2
    font = base64.b64encode(FONT.read_bytes()).decode()
    counts = funnel_counts()
    for name in ("light", "dark"):
        palette = brand_tokens.theme(name)
        suffix = "" if name == "light" else "-dark"
        for stem, drawing in (
            ("flow", flow(palette)),
            ("agent-vs-you", agent_vs_you(palette)),
            ("funnel", funnel(palette, counts)),
        ):
            (IMAGES / f"{stem}{suffix}.svg").write_text(drawing.svg(font))
    print("Funnel (example data):", counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
