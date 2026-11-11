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
      // Becomes "Today" when the home screen is rebuilt (stage 2).
      { id: "overview", label: "Overview" },
      { id: "applications", label: "Applications", count: "ready" },
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
export const TAB_BAR = ["overview", "applications", "inbox", "activity"];

/** Titles of the screens, by route. */
export const SCREENS: Record<string, string> = {
  overview: "Overview",
  applications: "Applications",
  inbox: "Inbox",
  shortlist: "Shortlist",
  activity: "Activity",
  career: "Career",
  policy: "Policy",
  templates: "Templates",
  collection: "Collection",
  settings: "Settings",
};

/** Names from the approved design that do not have their own screen yet. */
export const ALIASES: Record<string, string> = {
  today: "overview",
  jobs: "inbox",
};

/** Screens built with the design system; the others keep the older stylesheet. */
export const REBUILT = ["career", "policy", "templates"];

export const HOME = "overview";

/** The screen a location hash shows; an unknown route shows the home screen. */
export function routeOf(hash: string) {
  const name = hash.replace(/^#/, "").split("?")[0];
  const route = ALIASES[name] ?? name;
  return route in SCREENS ? route : HOME;
}

/** The hash rewritten to its canonical route, keeping the query; null if it already is. */
export function canonicalHash(hash: string) {
  const [name, query] = hash.replace(/^#/, "").split("?");
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

/** An object opened over the current screen, from `?job=` or `?application=`. */
export function overlayOf(hash: string) {
  const params = new URLSearchParams(hash.split("?")[1] || "");
  const job = params.get("job"),
    application = params.get("application");
  return job
    ? { kind: "job" as const, id: job }
    : application
      ? { kind: "application" as const, id: application }
      : null;
}
