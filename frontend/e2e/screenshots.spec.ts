import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, request, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";

import { SHOTS_URL } from "../playwright.config";

/**
 * Documentation screenshots. Runs only as `npm run screenshots`: it seeds a
 * fictional archive on its own server and writes PNGs to docs/images/.
 * Nothing here is real data.
 */

const OUT = fileURLToPath(new URL("../../docs/images/", import.meta.url));

interface Demo {
  title: string;
  company: string;
  location: string;
  description: string;
  status: string;
  labels?: string[];
  job_type?: string;
  is_remote?: boolean;
  min_amount?: number;
  max_amount?: number;
  currency?: string;
  date_posted?: string;
  note?: string;
}

const DEMO: Demo[] = [
  {
    title: "Backend Engineer, Data Platform",
    company: "Nordwind Labs",
    location: "Zurich, Switzerland",
    description:
      "## About the role\n\nYou will own the ingestion services behind our analytics platform: **Python** services on PostgreSQL and Kafka, deployed on Kubernetes.\n\n## What we look for\n\n- Three or more years building backend systems in production\n- Comfort with distributed systems and data pipelines\n- Fluent English; German is a plus, not a requirement",
    status: "new",
    job_type: "fulltime",
    min_amount: 120000,
    max_amount: 140000,
    currency: "CHF",
    date_posted: "2026-09-06",
  },
  {
    title: "Site Reliability Engineer",
    company: "Helvetic Cloud",
    location: "Remote (EMEA)",
    description:
      "Keep a multi-region platform up: Go and Python services, Terraform, observability, distributed systems. Remote across EMEA.",
    status: "new",
    job_type: "fulltime",
    is_remote: true,
    date_posted: "2026-09-07",
  },
  {
    title: "Software Engineer, Search Infrastructure",
    company: "Lumen Robotics",
    location: "Lausanne, Switzerland",
    description:
      "Vector search and ranking for a robotics fleet. Backend engineer profile: Rust and Python, PostgreSQL, gRPC, distributed systems.",
    status: "new",
    job_type: "fulltime",
    date_posted: "2026-09-05",
    labels: ["referral"],
  },
  {
    title: "Data Engineer",
    company: "Alpine Data AG",
    location: "Basel, Switzerland",
    description:
      "Data engineer for batch and streaming data pipelines with Python and Spark. Fluent in German required.",
    status: "new",
    job_type: "fulltime",
    date_posted: "2026-09-04",
  },
  {
    title: "Security Engineer, Platform",
    company: "Quantia",
    location: "Geneva, Switzerland",
    description:
      "Software engineer hardening a payments platform: threat modelling, SDLC gates, Kubernetes security, Python tooling.",
    status: "new",
    job_type: "fulltime",
    date_posted: "2026-09-03",
  },
  {
    title: "Machine Learning Engineer Intern",
    company: "Bluefjord",
    location: "Zug, Switzerland",
    description:
      "Six-month internship on model serving and evaluation tooling. PyTorch, Python, TypeScript dashboards.",
    status: "new",
    job_type: "internship",
    date_posted: "2026-09-02",
  },
  {
    title: "Platform Engineer",
    company: "Nordwind Labs",
    location: "Zurich, Switzerland",
    description:
      "Platform engineer on the developer platform team: CI, Kubernetes, internal tooling in Go and Python, PostgreSQL.",
    status: "shortlisted",
    job_type: "fulltime",
    labels: ["priority"],
    date_posted: "2026-08-30",
  },
  {
    title: "Backend Engineer, Payments",
    company: "Quantia",
    location: "Geneva, Switzerland",
    description:
      "Backend engineer: Python and PostgreSQL services processing card transactions. Distributed systems, remote-friendly.",
    status: "shortlisted",
    job_type: "fulltime",
    date_posted: "2026-08-28",
  },
  {
    title: "Senior Software Engineer, Observability",
    company: "Helvetic Cloud",
    location: "Remote (EMEA)",
    description:
      "Software engineer for metrics, traces and logs at scale: Go, Python, ClickHouse, OpenTelemetry, distributed systems. Remote.",
    status: "applied",
    job_type: "fulltime",
    is_remote: true,
    labels: ["dossier"],
    date_posted: "2026-08-20",
    note: "Applied through the careers page with the tailored CV; recruiter call booked for Thursday.",
  },
  {
    title: "Database Platform Engineer",
    company: "Alpine Data AG",
    location: "Basel, Switzerland",
    description:
      "Backend engineer running PostgreSQL at scale: high availability, backups, performance, Python automation.",
    status: "applied",
    job_type: "fulltime",
    labels: ["dossier"],
    date_posted: "2026-08-18",
  },
  {
    title: "Research Engineer, Distributed Systems",
    company: "Lumen Robotics",
    location: "Lausanne, Switzerland",
    description:
      "Software engineer prototyping coordination protocols for robot fleets: distributed systems, Python, Go; publish and ship.",
    status: "interviewing",
    job_type: "fulltime",
    labels: ["dossier"],
    date_posted: "2026-08-10",
  },
  {
    title: "Full-Stack Engineer",
    company: "Bluefjord",
    location: "Zug, Switzerland",
    description:
      "Software engineer: TypeScript and Python across a small product team. 10+ years required.",
    status: "rejected",
    job_type: "fulltime",
    date_posted: "2026-07-30",
  },
];

async function seed(api: APIRequestContext): Promise<string> {
  let applied = "";
  for (const [index, demo] of DEMO.entries()) {
    const response = await api.post("/api/jobs", {
      data: {
        ...demo,
        job_url: `https://careers.example.com/${demo.company.toLowerCase().replace(/[^a-z]+/g, "-")}/${index + 100}`,
        source: index % 3 === 0 ? "linkedin" : index % 3 === 1 ? "greenhouse" : "ashby",
      },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    const { job_ids } = (await response.json()) as { job_ids: string[] };
    if (demo.title.startsWith("Senior Software Engineer, Observability")) {
      applied = job_ids[0];
    }
  }
  await api.post(`/api/jobs/${applied}/attachments`, {
    multipart: {
      file: { name: "CV.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 demo") },
      kind: "cv",
      note: "tailored for the observability role",
    },
  });
  await api.post(`/api/jobs/${applied}/attachments`, {
    multipart: {
      file: {
        name: "cover-letter.md",
        mimeType: "text/markdown",
        buffer: Buffer.from(
          "# Cover letter\n\nDear team,\n\nI run a small observability stack myself and would like to do it at your scale.\n",
        ),
      },
      kind: "cover_letter",
    },
  });
  await api.post(`/api/jobs/${applied}/notes`, {
    data: {
      kind: "qa",
      title: "Why this role?",
      body: "Because the stack is the one I already operate for my own projects.",
    },
  });
  await api.post(`/api/jobs/${applied}/notes`, {
    data: { kind: "qa", title: "Notice period?", body: "Available from the first of next month." },
  });
  return applied;
}

async function shoot(page: Page, name: string, url: string, fullPage = false): Promise<void> {
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(400);
  await page.screenshot({ path: resolve(OUT, `${name}.png`), fullPage });
}

test.describe("documentation screenshots", () => {
  test.skip(!process.env.SCREENSHOTS, "run with npm run screenshots");
  test.describe.configure({ mode: "serial" });

  let applied = "";
  test.beforeAll(async () => {
    mkdirSync(OUT, { recursive: true });
    const api = await request.newContext({ baseURL: SHOTS_URL });
    applied = await seed(api);
    await api.dispose();
  });

  test("desktop, light and dark", async ({ browser }) => {
    for (const scheme of ["light", "dark"] as const) {
      const context = await browser.newContext({
        viewport: { width: 1280, height: 800 },
        colorScheme: scheme,
        baseURL: SHOTS_URL,
      });
      const page = await context.newPage();
      await shoot(page, `inbox-${scheme}`, "/?view=inbox");
      await shoot(page, `pipeline-${scheme}`, "/?view=pipeline");
      await shoot(page, `job-${scheme}`, `/?view=inbox&job=${applied}`);
      await shoot(page, `application-${scheme}`, `/?view=inbox&job=${applied}&tab=application`);
      await context.close();
    }
  });

  test("phone", async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
      baseURL: SHOTS_URL,
    });
    const page = await context.newPage();
    await shoot(page, "phone-inbox", "/?view=inbox");
    await shoot(page, "phone-pipeline", "/?view=pipeline");
    await shoot(page, "phone-job", `/?view=inbox&job=${applied}&tab=application`);
    await context.close();
  });
});
