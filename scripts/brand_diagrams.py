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


STEPS = (
    (
        "Openings, on your schedule",
        "Fresh jobs, no duplicates",
        "from your searches and watched companies",
        [
            "LinkedIn, Indeed and Glassdoor searches,",
            "careers pages on 12 hiring platforms, RSS",
            "and job links, into Jobs › New.",
        ],
    ),
    (
        "Your agent over MCP, or you by hand",
        "Your agent prepares",
        "Claude Code, Codex or any MCP client",
        [
            "Shortlists by your Preferences, with a",
            "reason for each dismissal, and tailors",
            "each CV and letter until it is Ready.",
        ],
    ),
    (
        "You",
        "You apply, best first",
        "on the employer's site",
        [
            "Ready is ranked by priority and deadline.",
            "Apply with everything prepared, then",
            "track the reply.",
        ],
    ),
)


def flow(palette):
    d = Drawing(
        440,
        "Fresh jobs, no duplicates; your agent prepares; you apply, best first. "
        "Openings collects jobs into Jobs › New, your agent shortlists and tailors each "
        "CV and letter over MCP, and you apply on the employer's site, ranked by priority "
        "and deadline.",
        palette,
    )
    for index, (who, title, caption, body) in enumerate(STEPS):
        x, last = 20 + index * 400, index == 2
        ink = "text" if last else "accent-text"
        d.text(x + 180, 40, who, size=16, weight=MEDIUM, colour=ink, anchor="middle")
        d.path(f"M{x} 66V58H{x + 360}V66", stroke="text" if last else "accent", width=1.5)
        if last:
            d.rect(x, 92, 360, 106, fill="primary", radius=12)
        else:
            d.rect(x, 92, 360, 106, fill="accent-soft", stroke="accent", radius=12)
        sub = "on-primary" if last else "text-2"
        d.text(x + 24, 124, str(index + 1), size=14, weight=MEDIUM, colour=sub)
        d.text(x + 24, 156, title, size=24, weight=SEMIBOLD, colour=sub if last else "text")
        d.text(x + 24, 180, caption, size=14, weight=MEDIUM, colour=sub)
        d.text(x + 24, 232, body, size=15, colour="text-2", lead=22)
        if not last:
            d.arrow(x + 366, x + 394, 145)
    d.path(f"M20 320H{WIDTH - 20}", stroke="border", width=1)
    d.rect(22, 348, 16, 16, fill="accent-soft", stroke="accent", radius=4)
    d.text(
        50,
        361,
        "Every step works by hand in the dashboard, from scripts with the REST API, "
        "or with your agent over MCP.",
        size=15,
        colour="text-2",
    )
    d.rect(22, 384, 16, 16, fill="primary", radius=4)
    d.text(
        50,
        397,
        "Nothing in Openings can submit an application or contact an employer.",
        size=15,
        colour="text-2",
    )
    return d


AGENT = (
    (
        "Triages with reasons",
        ["goes through Jobs › New by your Preferences,", "with a reason for every dismissal"],
    ),
    (
        "Writes and compiles",
        ["the tailored CV and letter from your career", "record, as PDFs, until it is Ready"],
    ),
    (
        "Sets priority, deadline and salary range",
        ["so Ready reads best first; a range only", "with a note of its evidence"],
    ),
    ("Records what you tell it", ["replies, interviews and outcomes"]),
    (
        "Reports back",
        ["what is Ready, what needs you, what it changed;", "every write is attributed"],
    ),
)
YOU = (
    ("Say what you want", ["Preferences and standing rules,", "in your own words"]),
    ("Apply on the employer's site", ["best first, with everything prepared"]),
    ("Decide what it may do on its own", ["when to act, when to ask first,", "and how to undo"]),
    ("Own the data", ["one SQLite file on your machine,", "with daily verified backups"]),
)


def agent_vs_you(palette):
    d = Drawing(
        664,
        "Your agent and you. Your agent, over MCP: triages with reasons, writes and "
        "compiles, sets priority, deadline and salary range, records what you tell it and "
        "reports back. You: say what you want, apply on the employer's site, decide what "
        "it may do on its own, own the data. Nothing in Openings can apply for you.",
        palette,
    )
    d.rect(20, 20, 680, 500, fill="accent-soft", stroke="accent", radius=12)
    d.text(52, 66, "Your agent, over MCP", size=26, weight=SEMIBOLD)
    d.text(
        52,
        94,
        "Claude Code, Codex or any MCP client. No AI runs inside Openings.",
        size=15,
        weight=MEDIUM,
        colour="accent-text",
    )
    y = 140
    for title, body in AGENT:
        d.check(54, y - 6)
        d.text(84, y, title, size=17, weight=MEDIUM)
        d.text(84, y + 25, body, size=15, colour="text-2", lead=22)
        y += 38 + 22 * len(body)
    d.rect(724, 20, 456, 500, fill="surface", stroke="text", radius=12)
    d.text(756, 66, "You", size=26, weight=SEMIBOLD)
    d.text(
        756, 94, "The part worth your time. The rest works by hand too.", size=15, colour="text-2"
    )
    y = 140
    for title, body in YOU:
        d.dot(762, y - 6)
        d.text(784, y, title, size=17, weight=MEDIUM)
        d.text(784, y + 25, body, size=15, colour="text-2", lead=22)
        y += 38 + 22 * len(body)
    d.rect(20, 544, WIDTH - 40, 100, fill="bg-subtle", stroke="border", radius=12)
    d.text(52, 580, "Nothing in Openings can apply for you.", size=18, weight=SEMIBOLD)
    d.text(
        52,
        608,
        [
            "No operation sends anything to an employer, by you or by your agent.",
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
