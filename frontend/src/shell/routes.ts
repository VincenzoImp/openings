// The route table: every screen's hash route, its title and where it sits in
// the navigation. Pure (no React), so the matching is tested directly. There
// are no aliases: an address that matches no route opens Today.
//
//   #jobs?job=…          a screen, with its state in the query
//   #applications/AP-1   a second-level page, with a path parameter

export type RouteId =
  | "today"
  | "jobs"
  | "applications"
  | "application"
  | "profile"
  | "preferences"
  | "templates"
  | "sources"
  | "settings"
  | "setup";

export interface RouteDef {
  id: RouteId;
  /** Segments; `:name` is a parameter. */
  path: string;
  title: string;
  /** A second-level page: its parent, for the breadcrumb and the back chevron. */
  parent?: RouteId;
  /** The navigation item shown as current; none during the first-run setup. */
  nav: RouteId | null;
}

export const ROUTES: Record<RouteId, RouteDef> = {
  today: { id: "today", path: "today", title: "Today", nav: "today" },
  jobs: { id: "jobs", path: "jobs", title: "Jobs", nav: "jobs" },
  applications: {
    id: "applications",
    path: "applications",
    title: "Applications",
    nav: "applications",
  },
  application: {
    id: "application",
    path: "applications/:id",
    title: "Application",
    parent: "applications",
    nav: "applications",
  },
  profile: { id: "profile", path: "profile", title: "Profile", nav: "profile" },
  preferences: {
    id: "preferences",
    path: "preferences",
    title: "Preferences",
    nav: "preferences",
  },
  templates: {
    id: "templates",
    path: "templates",
    title: "Templates",
    nav: "templates",
  },
  sources: { id: "sources", path: "sources", title: "Sources", nav: "sources" },
  settings: {
    id: "settings",
    path: "settings",
    title: "Settings",
    nav: "settings",
  },
  setup: {
    id: "setup",
    path: "setup",
    title: "Set up",
    parent: "today",
    nav: null,
  },
};

export const HOME: RouteId = "today";

export interface Route {
  id: RouteId;
  def: RouteDef;
  params: Record<string, string>;
  query: URLSearchParams;
  /** The hash it was read from, without `#`. */
  hash: string;
}

/** The route a hash names, or null when it names none. */
export function match(hash: string): Route | null {
  const raw = hash.replace(/^#\/?/, "");
  const [path, search = ""] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  for (const def of Object.values(ROUTES)) {
    const pattern = def.path.split("/");
    if (pattern.length !== parts.length) continue;
    const params: Record<string, string> = {};
    const ok = pattern.every((segment, index) => {
      if (segment.startsWith(":")) {
        try {
          params[segment.slice(1)] = decodeURIComponent(parts[index]);
        } catch {
          return false;
        }
        return true;
      }
      return segment === parts[index];
    });
    if (ok)
      return {
        id: def.id,
        def,
        params,
        query: new URLSearchParams(search),
        hash: raw,
      };
  }
  return null;
}

/** The route a hash shows: an unknown or empty one shows Today. */
export function resolve(hash: string): Route {
  return match(hash) ?? match(HOME)!;
}

/** The hash of a route: href("application", { id }, { tab: "documents" }). */
export function href(
  id: RouteId,
  params: Record<string, string> = {},
  query: Record<string, string | undefined> = {},
) {
  const path = ROUTES[id].path
    .split("/")
    .map((segment) =>
      segment.startsWith(":")
        ? encodeURIComponent(params[segment.slice(1)] ?? "")
        : segment,
    )
    .join("/");
  const search = new URLSearchParams(
    Object.entries(query).filter(
      (entry): entry is [string, string] => !!entry[1],
    ),
  ).toString();
  return `#${path}${search ? "?" + search : ""}`;
}

/** The trail of a second-level page: its parent, then itself. */
export function breadcrumb(route: Route, title = route.def.title) {
  const parent = route.def.parent && ROUTES[route.def.parent];
  return parent
    ? [{ label: parent.title, href: href(parent.id) }, { label: title }]
    : [];
}
