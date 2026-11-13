// What the setup guide shows, derived from the workspace alone: which steps
// are done, what each part of the record holds and where to start. No React:
// tested directly.
import type { NoReply, PreferenceSection } from "../../api.ts";

export type StepId = "agent" | "record" | "next";
export type ItemId =
  "profile" | "preferences" | "searches" | "entries" | "claims" | "templates";
export type ItemState = "done" | "progress" | "todo";

export interface SetupToken {
  name: string;
  kind: string;
  created_at: string;
  last_used_at?: string | null;
}
/** Everything the guide reads; counts are totals. */
export interface SetupFacts {
  profile: { name: string; headline: string; location: string; email: string };
  sections: Pick<PreferenceSection, "section" | "items">[];
  noReply: NoReply | null;
  sources: number;
  tokens: SetupToken[];
  entries: number;
  claims: number;
  templates: number;
  applications: number;
}

const plural = (count: number, one: string, many = `${one}s`) =>
  `${count} ${count === 1 ? one : many}`;
const sectionTotal = (facts: SetupFacts, name: string) =>
  facts.sections.find((section) => section.section === name)?.items.length ?? 0;

/**
 * The agent is connected once one of its tokens made a call: the newest
 * token used, else the newest token, else none.
 */
export function connection(tokens: SetupToken[]) {
  const newest = (list: SetupToken[], key: "created_at" | "last_used_at") =>
    [...list].sort((a, b) =>
      String(b[key] ?? "").localeCompare(String(a[key] ?? "")),
    )[0];
  const used = tokens.filter((token) => token.last_used_at);
  if (used.length)
    return { state: "done" as const, token: newest(used, "last_used_at") };
  if (tokens.length)
    return { state: "waiting" as const, token: newest(tokens, "created_at") };
  return { state: "todo" as const, token: null };
}

export interface RecordItem {
  id: ItemId;
  title: string;
  meta: string;
  state: ItemState;
}

/** The parts of the record, in the order the agent builds them. */
export function recordItems(facts: SetupFacts): RecordItem[] {
  const { profile } = facts;
  const named = profile.name.trim();
  const lookingFor = sectionTotal(facts, "looking_for");
  const ruledOut = sectionTotal(facts, "ruled_out");
  const items = facts.sections.reduce(
    (sum, section) => sum + section.items.length,
    0,
  );
  const reply = facts.noReply?.source === "settings";
  const count = (
    id: ItemId,
    title: string,
    total: number,
    meta: string,
    empty: string,
  ): RecordItem => ({
    id,
    title,
    meta: total ? meta : empty,
    state: total ? "done" : "todo",
  });
  return [
    {
      id: "profile",
      title: "Profile",
      meta: named
        ? [named, profile.headline.trim()].filter(Boolean).join(" · ")
        : "Your name, headline, place and email: what every document starts from.",
      state: named
        ? "done"
        : profile.headline || profile.location || profile.email
          ? "progress"
          : "todo",
    },
    {
      id: "preferences",
      title: "Preferences",
      meta:
        items || reply
          ? [
              plural(lookingFor, "statement") + " on what you look for",
              `${ruledOut} you rule out`,
              reply
                ? `no reply after ${plural(facts.noReply!.days, "day")}`
                : "no reply period not set",
            ].join(" · ")
          : "What you are looking for, what you rule out, and when an application counts as unanswered.",
      state:
        lookingFor && reply ? "done" : items || reply ? "progress" : "todo",
    },
    count(
      "searches",
      "First searches",
      facts.sources,
      plural(
        facts.sources,
        "saved search or company board",
        "saved searches and company boards",
      ),
      "A saved search, or the job board of a company you follow.",
    ),
    count(
      "entries",
      "Career entries",
      facts.entries,
      plural(facts.entries, "entry", "entries") +
        " about your experience, education and projects.",
      "Your experience, education and projects, with their dates.",
    ),
    count(
      "claims",
      "Claims",
      facts.claims,
      plural(facts.claims, "statement") +
        " about your work, for documents to use.",
      "Statements about your work that a CV or letter may use.",
    ),
    count(
      "templates",
      "Templates",
      facts.templates,
      plural(facts.templates, "template") + " for your CV and letters.",
      "A CV and a letter template, from the layout of your CV.",
    ),
  ];
}

/** Each step's state and the line under its name. */
export function steps(facts: SetupFacts) {
  const agent = connection(facts.tokens);
  const items = recordItems(facts);
  const done = items.filter((item) => item.state === "done").length;
  return {
    agent: {
      done: agent.state === "done",
      line:
        agent.state === "done"
          ? `Done · ${agent.token!.name}`
          : agent.state === "waiting"
            ? "Waiting for the first call"
            : "Not started",
    },
    record: {
      done: done === items.length,
      line:
        done === items.length
          ? "Done"
          : done
            ? `In progress · ${done} of ${items.length}`
            : "Not started",
    },
    next: {
      done: facts.applications > 0,
      line: facts.applications
        ? plural(facts.applications, "application")
        : "After the record",
    },
  };
}

/** Where the guide opens: the first step that is not done. */
export function firstStep(facts: SetupFacts): StepId {
  const state = steps(facts);
  if (!state.agent.done && !state.record.done) return "agent";
  if (!state.record.done) return "record";
  return state.agent.done ? "next" : "agent";
}

/** Every step is done: the guide has nothing left to ask. */
export function setupComplete(facts: SetupFacts) {
  const state = steps(facts);
  return state.agent.done && state.record.done;
}
