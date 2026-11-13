// The information architecture in one place: groups, destinations and the hash
// routes that reach them. Every route that ever shipped keeps working; a
// renamed or merged destination becomes an alias, never a dead link.

export interface Destination {
  /** The hash route, and the id of the screen it shows. */
  id: string;
  label: string;
  /** Routes shown under this destination (the two queues of Jobs). */
  routes?: string[];
  /** Which number the navigation shows beside the label. */
  count?: "ready" | "questions" | "inbox";
}
export interface NavGroup {
  group: string;
  items: Destination[];
}

export const NAV: NavGroup[] = [
  {
    group: "Work",
    items: [
      { id: "today", label: "Today" },
      // The review page of one application belongs to Applications.
      {
        id: "applications",
        label: "Applications",
        routes: ["applications", "review"],
        count: "ready",
      },
      // Inbox and Shortlist are the two queues of one Jobs destination; the
      // page keeps both routes until it is rebuilt (stage 4).
      {
        id: "inbox",
        label: "Jobs",
        routes: ["inbox", "shortlist"],
        count: "inbox",
      },
      { id: "activity", label: "Activity", count: "questions" },
    ],
  },
  {
    group: "Library",
    items: [
      { id: "career", label: "Career" },
      { id: "policy", label: "Policy" },
      { id: "templates", label: "Templates" },
    ],
  },
  {
    group: "System",
    items: [
      { id: "collection", label: "Collection" },
      { id: "settings", label: "Settings" },
    ],
  },
];

/** The destinations of the bottom bar on narrow screens; the rest is under More. */
export const TAB_BAR = ["today", "applications", "inbox", "activity"];

/** Titles of the screens, by route. */
export const SCREENS: Record<string, string> = {
  today: "Today",
  applications: "Applications",
  review: "Application review",
  inbox: "Inbox",
  shortlist: "Shortlist",
  activity: "Activity",
  career: "Career",
  policy: "Policy",
  templates: "Templates",
  collection: "Collection",
  settings: "Settings",
};

/**
 * Other names of a screen: the one it had in an earlier version (Overview is
 * now Today) and names from the approved design without their own screen yet.
 */
export const ALIASES: Record<string, string> = {
  overview: "today",
  jobs: "inbox",
  skills: "settings",
};

/** Screens built with the design system; the others keep the older stylesheet. */
export const REBUILT = [
  "today",
  "applications",
  "review",
  "activity",
  "career",
  "policy",
  "templates",
  "collection",
  "settings",
];

export const HOME = "today";

/** The screen a location hash shows; an unknown route shows the home screen. */
export function routeOf(hash: string) {
  const [name, query = ""] = hash.replace(/^#/, "").split("?");
  // An application is shown on its own page, from any screen's address.
  if (new URLSearchParams(query).has("application")) return "review";
  const route = ALIASES[name] ?? name;
  return route in SCREENS ? route : HOME;
}

// The stage filter of the old Applications page: Preparing no longer includes
// the Ready applications, and `readiness=ready` alone was the Ready queue.
const OLD_STAGES: Record<string, string> = {
  draft: "preparing",
  applied: "applied",
  interview: "interview",
  offer: "offer",
  closed: "closed",
};
function upgradeApplications(params: URLSearchParams) {
  let changed = false;
  const status = params.get("status");
  if (status) {
    params.delete("status");
    params.set("stage", OLD_STAGES[status] || "all");
    changed = true;
  }
  const stage = params.get("stage");
  if (params.get("readiness") === "ready" && (!stage || stage === "all")) {
    params.delete("readiness");
    params.set("stage", "ready");
    changed = true;
  }
  return changed;
}

/**
 * The query of a System screen in an earlier version, rewritten: the provider
 * settings and the task list of the old Settings moved to Collection, and the
 * two lists of the old Collection (saved searches, companies) are one list of
 * sources filtered by kind. Returns the new hash, or null.
 */
function upgradeSystem(name: string, params: URLSearchParams) {
  const section = params.get("section");
  if (name === "skills") {
    params.set("section", "skills");
    return `#settings?${params}`;
  }
  if (name === "settings" && section === "collection")
    return "#collection?section=providers";
  if (name === "settings" && section === "activity") {
    params.set("section", "runs");
    const view = params.get("activity_view");
    params.delete("activity_view");
    if (view === "tasks") params.set("view", "tasks");
    return `#collection?${params}`;
  }
  if (
    name === "collection" &&
    (section === "searches" || section === "companies")
  ) {
    params.delete("section");
    params.set("kind", section === "searches" ? "search" : "board");
    return `#collection?${params}`;
  }
  return null;
}

/**
 * The hash rewritten to its canonical route, keeping the query; null if it
 * already is. An application opened over any screen (`?application=`, the old
 * drawer, with `detail=` for its tab) is its review page, the old
 * Overview's period (`#overview?since=`) is the Progress of Insights, and
 * the moved parts of Settings and Collection open where they are now.
 */
export function canonicalHash(hash: string) {
  const [name, query = ""] = hash.replace(/^#/, "").split("?");
  const params = new URLSearchParams(query);
  const application = params.get("application");
  if (application && name !== "review") {
    const next = new URLSearchParams({ application });
    const detail = params.get("detail");
    if (detail === "posting") next.set("pane", "posting");
    else if (detail) next.set("tab", detail);
    return `#review?${next}`;
  }
  if (name === "overview" && (params.has("since") || params.has("until"))) {
    params.set("section", "insights");
    return `#applications?${params}`;
  }
  if (name === "applications" && upgradeApplications(params))
    return `#applications?${params}`;
  const system = upgradeSystem(name, params);
  if (system) return system;
  if (!(name in ALIASES)) return null;
  return `#${ALIASES[name]}${query ? "?" + query : ""}`;
}

export function destinationOf(route: string) {
  for (const group of NAV)
    for (const item of group.items)
      if (item.id === route || item.routes?.includes(route))
        return { group: group.group, item };
  return null;
}

/** A job opened over the current screen, from `?job=`. */
export function overlayOf(hash: string) {
  const job = new URLSearchParams(hash.split("?")[1] || "").get("job");
  return job ? { kind: "job" as const, id: job } : null;
}
