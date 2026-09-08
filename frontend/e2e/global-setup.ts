import { Api } from "./api";
import type { SeedJob } from "./api";

/**
 * The fixture every spec can rely on. Titles start with "E2E" so tests can
 * search for them; the URLs are stable so a re-run updates instead of
 * duplicating.
 */
export const SEED: Record<string, SeedJob> = {
  backend: {
    title: "E2E Backend Engineer",
    company: "Acme",
    location: "Zurich, Switzerland",
    job_url: "https://e2e.example.com/seed/backend",
    description:
      "## About\n\nWe are hiring a **backend engineer** to build Python services on PostgreSQL. Remote friendly.",
    status: "new",
    labels: ["e2e"],
  },
  data: {
    title: "E2E Data Engineer",
    company: "Beta",
    location: "Remote",
    job_url: "https://e2e.example.com/seed/data",
    description: "Data engineer building a data pipeline in Python.",
    status: "new",
  },
  frontend: {
    title: "E2E Frontend Engineer",
    company: "Gamma",
    location: "Berlin, Germany",
    job_url: "https://e2e.example.com/seed/frontend",
    description: "TypeScript and React. Fluent in German required.",
    status: "new",
  },
  sales: {
    title: "E2E Sales Manager",
    company: "Delta",
    location: "London, UK",
    job_url: "https://e2e.example.com/seed/sales",
    description: "Enterprise sales, 10+ years of quota carrying experience.",
    status: "new",
  },
  research: {
    title: "E2E Research Scientist",
    company: "Epsilon",
    location: "Lausanne, Switzerland",
    job_url: "https://e2e.example.com/seed/research",
    description: "Distributed systems research on data pipelines.",
    status: "new",
  },
  platform: {
    title: "E2E Platform Engineer",
    company: "Acme",
    location: "Zurich, Switzerland",
    job_url: "https://e2e.example.com/seed/platform",
    description: "Platform team, Python and TypeScript.",
    status: "shortlisted",
    labels: ["e2e", "priority"],
  },
  sre: {
    title: "E2E Site Reliability Engineer",
    company: "Zeta",
    location: "Remote",
    job_url: "https://e2e.example.com/seed/sre",
    description: "Keep the distributed systems up. Python, PostgreSQL.",
    status: "applied",
    note: "Applied through the careers page with the tailored CV.",
  },
  security: {
    title: "E2E Security Engineer",
    company: "Eta",
    location: "Geneva, Switzerland",
    job_url: "https://e2e.example.com/seed/security",
    description: "Application security for a software engineer team.",
    status: "interviewing",
  },
  mobile: {
    title: "E2E Mobile Engineer",
    company: "Theta",
    location: "Milan, Italy",
    job_url: "https://e2e.example.com/seed/mobile",
    description: "iOS and Android.",
    status: "rejected",
  },
  spam: {
    title: "E2E Recruiter Spam",
    company: "Iota",
    location: "Anywhere",
    job_url: "https://e2e.example.com/seed/spam",
    description: "Unlimited earning potential.",
    status: "new",
  },
};

export default async function globalSetup(): Promise<void> {
  const api = await Api.plain();
  const ids: Record<string, string> = {};
  for (const [key, job] of Object.entries(SEED)) {
    ids[key] = await api.addJob(job);
  }
  await api.addNote(ids.sre, "qa", "Because the stack matches.", "Why do you want to join?");
  await api.upload(ids.sre, "cv.txt", "Curriculum vitae for the SRE role.\n", "cv");
  await api.upload(ids.sre, "cover-letter.md", "# Cover letter\n\nDear team,\n", "cover_letter");
  await api.blacklist([ids.spam]);
  await api.dispose();

  const token = await Api.token();
  await token.addJob({
    title: "E2E Token Gated Posting",
    company: "Kappa",
    location: "Remote",
    job_url: "https://e2e.example.com/seed/token",
    description: "Only visible with the token.",
    status: "new",
  });
  await token.dispose();
}
