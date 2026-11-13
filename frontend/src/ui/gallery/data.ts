// Synthetic records for the gallery. No real people, companies or postings.
import type { Stage } from "../Icon";

const HOUR = 3_600_000;
const DAY = 24 * HOUR;
/** A fixed "now" so the gallery reads the same on every run. */
export const NOW = new Date(2026, 10, 14, 15, 0);
const ago = (ms: number) => new Date(NOW.getTime() - ms);
const at = (month: number, day: number) => new Date(2026, month, day, 9, 0);

export interface DemoJob {
  id: string;
  title: string;
  company: string;
  place: string;
  found: Date;
  unread?: boolean;
  duplicate?: boolean;
  incomplete?: boolean;
  closes?: Date;
}

export const JOB_GROUPS: { label: string; jobs: DemoJob[] }[] = [
  {
    label: "Today",
    jobs: [
      {
        id: "j1",
        title: "Senior Machine Learning Infrastructure Engineer",
        company: "International Example Consortium",
        place: "Geneva",
        found: ago(2 * HOUR),
        unread: true,
      },
      {
        id: "j2",
        title: "Data Engineer, Grid Platform",
        company: "Northstar Labs",
        place: "Zurich",
        found: ago(3 * HOUR),
        duplicate: true,
      },
      {
        id: "j3",
        title: "Python Engineer",
        company: "Northstar Labs",
        place: "Zurich",
        found: ago(5 * HOUR),
        unread: true,
      },
      {
        id: "j4",
        title: "Software Engineer, Data",
        company: "Kestrel Robotics",
        place: "Zurich",
        found: ago(8 * HOUR),
        unread: true,
        incomplete: true,
      },
    ],
  },
  {
    label: "Yesterday",
    jobs: [
      {
        id: "j5",
        title: "Data Platform Engineer",
        company: "Fjord Analytics",
        place: "Remote, Europe",
        found: ago(DAY + 2 * HOUR),
        closes: at(10, 18),
      },
      {
        id: "j6",
        title: "Backend Engineer",
        company: "Lumen Health",
        place: "Basel",
        found: ago(DAY + 4 * HOUR),
      },
      {
        id: "j7",
        title: "Site Reliability Engineer",
        company: "Orbit Works",
        place: "Lausanne",
        found: ago(DAY + 6 * HOUR),
      },
    ],
  },
  {
    label: "Earlier",
    jobs: [
      {
        id: "j8",
        title: "Analytics Engineer",
        company: "Meridian Grid",
        place: "Bern",
        found: at(10, 10),
      },
      {
        id: "j9",
        title: "Data Engineer",
        company: "Orbit Analytics",
        place: "Zurich",
        found: at(10, 9),
      },
      {
        id: "j10",
        title: "Machine Learning Engineer, Forecasting",
        company: "Tidewater Energy",
        place: "Remote",
        found: at(10, 6),
      },
      {
        id: "j11",
        title: "Platform Engineer",
        company: "Cobalt Transit",
        place: "Winterthur",
        found: at(9, 28),
      },
    ],
  },
];

export interface DemoApplication {
  id: string;
  title: string;
  company: string;
  stage: Stage;
  deadline?: Date;
  overdue?: boolean;
}

export const APPLICATIONS: DemoApplication[] = [
  {
    id: "a1",
    title: "Python Engineer",
    company: "Northstar Labs",
    stage: "ready",
    deadline: at(10, 15),
  },
  {
    id: "a2",
    title: "Data Platform Engineer",
    company: "Fjord Analytics",
    stage: "ready",
    deadline: at(10, 18),
  },
  {
    id: "a3",
    title: "Data Engineer",
    company: "Orbit Analytics",
    stage: "shortlisted",
    deadline: at(11, 13),
  },
  {
    id: "a4",
    title: "Backend Engineer",
    company: "Lumen Health",
    stage: "applied",
  },
  {
    id: "a5",
    title: "Senior ML Infrastructure Engineer",
    company: "International Example Consortium",
    stage: "interview",
    deadline: at(10, 12),
    overdue: true,
  },
  {
    id: "a6",
    title: "Analytics Engineer",
    company: "Meridian Grid",
    stage: "offer",
  },
  {
    id: "a7",
    title: "Platform Engineer",
    company: "Cobalt Transit",
    stage: "closed",
  },
];

export const PROVIDERS = [
  { name: "Greenhouse", status: "Ready", tone: "success", spacing: 2, day: 142 },
  { name: "LinkedIn", status: "Waiting", tone: "warning", spacing: 30, day: 18 },
  { name: "Fjord board", status: "Failed", tone: "danger", spacing: 10, day: 0 },
  { name: "Lever", status: "Ready", tone: "success", spacing: 5, day: 1_204 },
] as const;

export const PROFILE = {
  name: "Alex Morgan",
  headline: "Data engineer · energy and climate data",
  location: "Zurich",
  email: "alex@example.com",
  site: "example.dev",
  summary:
    "Six years building data pipelines for utilities and grid operators. I like owning ingestion end to end, from raw meter feeds to the tables forecasters trust.",
  roles: "Data engineer, analytics engineer",
  locations: "Zurich, Basel, remote within Europe",
  languages: "English (fluent), German (B2), Italian (native)",
};
