// The information architecture in one place: groups, destinations and the hash
// routes that reach them. An unknown route opens the home screen.

export interface Destination {
  /** The hash route, and the id of the screen it shows. */
  id: string;
  label: string;
  /** Routes shown under this destination (the two queues of Jobs). */
  routes?: string[];
  /** Which number the navigation shows beside the label. */
  count?: "ready" | "questions" | "new";
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
      // New (the old Inbox), Shortlisted, Dismissed and All are tabs of Jobs.
      { id: "jobs", label: "Jobs", count: "new" },
      { id: "activity", label: "Activity", count: "questions" },
    ],
  },
  {
    group: "Library",
    items: [
      { id: "career", label: "Career" },
      { id: "preferences", label: "Preferences" },
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
export const TAB_BAR = ["today", "applications", "jobs", "activity"];

/** Titles of the screens, by route. */
export const SCREENS: Record<string, string> = {
  today: "Today",
  applications: "Applications",
  review: "Application review",
  jobs: "Jobs",
  activity: "Activity",
  career: "Career",
  preferences: "Preferences",
  templates: "Templates",
  collection: "Collection",
  settings: "Settings",
  setup: "Set up",
};

export const HOME = "today";

/** The screen a location hash shows; an unknown route shows the home screen. */
export function routeOf(hash: string) {
  const name = hash.replace(/^#/, "").split("?")[0];
  return name in SCREENS ? name : HOME;
}

export function destinationOf(route: string) {
  for (const group of NAV)
    for (const item of group.items)
      if (item.id === route || item.routes?.includes(route))
        return { group: group.group, item };
  return null;
}
