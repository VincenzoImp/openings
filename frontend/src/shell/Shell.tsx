import { useEffect, useRef, useState } from "react";
import type { ListResult, Run } from "../api";
import {
  confirmLeave,
  useFormProtection,
  useResource,
  useWorkspace,
} from "../state";
import { lockPageScroll } from "../design";
import { AgentStatus } from "./AgentStatus";
import { MoreSheet, Sidebar, TabBar } from "./Navigation";
import {
  AddJob,
  ApplicationsPage,
  ReviewPage,
  ActivityPage,
  CareerPage,
  CollectionPage,
  JobDrawer,
  JobsPage,
  Overlay as OverlayFrame,
  PolicyPage,
  Screen,
  SettingsPage,
  TemplatesPage,
  TodayPage,
} from "./Screens";
import { TopBar } from "./TopBar";
import {
  THEME_KEY,
  applyDensity,
  applyTheme,
  initialDensity,
  initialTheme,
  type Density,
  type Theme,
} from "./preferences";
import {
  HOME,
  REBUILT,
  SCREENS,
  canonicalHash,
  overlayOf,
  routeOf,
} from "./routes";

type Overlay = { kind: "add" } | { kind: "job"; id: string } | null;
const NARROW = "(max-width: 860px)";
const emptyList = { items: [], total: 0 };

function useNarrow() {
  const [narrow, setNarrow] = useState(() => matchMedia(NARROW).matches);
  useEffect(() => {
    const media = matchMedia(NARROW);
    const change = () => setNarrow(media.matches);
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);
  return narrow;
}

/** Theme and density as the owner chose them; the theme follows the system until then. */
function usePreferences() {
  const [theme, setTheme] = useState<Theme>(initialTheme),
    [density, setDensity] = useState<Density>(initialDensity);
  useEffect(() => {
    const media = matchMedia("(prefers-color-scheme: dark)");
    const follow = () => {
      let stored: string | null = null;
      try {
        stored = localStorage.getItem(THEME_KEY);
      } catch {}
      if (stored) return;
      const next = media.matches ? "dark" : "light";
      applyTheme(next, false);
      setTheme(next);
    };
    media.addEventListener("change", follow);
    return () => media.removeEventListener("change", follow);
  }, []);
  return {
    theme,
    density,
    toggleTheme: () => {
      const next = theme === "light" ? "dark" : "light";
      applyTheme(next);
      setTheme(next);
    },
    toggleDensity: () => {
      const next = density === "compact" ? "comfortable" : "compact";
      applyDensity(next);
      setDensity(next);
    },
  };
}

export function Shell({ onLogout }: { onLogout: () => Promise<void> }) {
  useFormProtection();
  const main = useRef<HTMLElement>(null),
    moreButton = useRef<HTMLButtonElement>(null);
  const lastRoute = useRef(location.hash);
  const [route, setRoute] = useState(() => routeOf(location.hash)),
    [more, setMore] = useState(false),
    [overlay, setOverlay] = useState<Overlay>(() => overlayOf(location.hash));
  const narrow = useNarrow();
  const { theme, density, toggleTheme, toggleDensity } = usePreferences();
  const { pending, refresh, notify } = useWorkspace();
  const inbox = useResource<ListResult<never>>(
      "/jobs?queue=inbox&limit=1",
      emptyList,
    ),
    questions = useResource<ListResult<never>>(
      "/questions?state=open&limit=1",
      emptyList,
    ),
    applications = useResource<ListResult<never>>(
      "/applications?status=draft&limit=1",
      emptyList,
    ),
    runs = useResource<ListResult<Run>>("/runs?status=open&limit=1", emptyList);

  useEffect(() => {
    // Another name of a screen (#overview, #jobs) is rewritten to the route that
    // shows it, so links and the Back button see one address per screen.
    const canonicalise = () => {
      const canonical = canonicalHash(location.hash);
      if (canonical) history.replaceState(null, "", canonical);
      return Boolean(canonical);
    };
    // A screen that already read the old address reads the rewritten one.
    const announce = () => window.dispatchEvent(new PopStateEvent("popstate"));
    const rewritten = canonicalise();
    lastRoute.current = location.hash;
    if (rewritten) announce();
    const listener = () => {
      if (location.hash === lastRoute.current) return;
      if (!confirmLeave()) {
        history.replaceState(null, "", lastRoute.current || `#${HOME}`);
        return;
      }
      const changed = canonicalise();
      lastRoute.current = location.hash;
      setRoute(routeOf(location.hash));
      setOverlay(overlayOf(location.hash));
      setMore(false);
      window.scrollTo(0, 0);
      if (changed) announce();
    };
    const remember = () => {
      lastRoute.current = location.hash;
    };
    window.addEventListener("openings:url", remember);
    window.addEventListener("hashchange", listener);
    window.addEventListener("popstate", listener);
    return () => {
      window.removeEventListener("openings:url", remember);
      window.removeEventListener("hashchange", listener);
      window.removeEventListener("popstate", listener);
    };
  }, []);
  useEffect(() => {
    document.title = `${SCREENS[route] || "Workspace"} · Openings`;
  }, [route]);
  // On a new screen, focus moves to its content, so a keyboard or screen
  // reader continues there instead of at the top of the navigation. An agent
  // works while the dashboard is open: recount questions and runs as well.
  const visited = useRef(route);
  useEffect(() => {
    if (visited.current === route) return;
    visited.current = route;
    main.current?.focus({ preventScroll: true });
    questions.reload();
    runs.reload();
  }, [route]);
  // The More sheet: Escape closes it, the page behind it does not scroll, and
  // it closes by itself when the window becomes wide.
  useEffect(() => {
    if (!more) return;
    const unlock = lockPageScroll();
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMore(false);
    };
    document.addEventListener("keydown", close);
    const button = moreButton.current;
    return () => {
      unlock();
      document.removeEventListener("keydown", close);
      // Focus returns to More unless a destination took it (a new screen).
      if (
        button?.isConnected &&
        (document.activeElement === document.body ||
          !document.activeElement?.isConnected)
      )
        button.focus({ preventScroll: true });
    };
  }, [more]);
  useEffect(() => {
    if (!narrow) setMore(false);
  }, [narrow]);

  function navigate(target: string, next: Overlay = null) {
    if (!confirmLeave()) return;
    const [id, query] = target.split("?");
    history.pushState(
      null,
      "",
      `#${id}${
        next && next.kind !== "add"
          ? `?${next.kind}=${encodeURIComponent(next.id)}`
          : query
            ? "?" + query
            : ""
      }`,
    );
    lastRoute.current = location.hash;
    setRoute(routeOf(location.hash));
    setOverlay(next);
    setMore(false);
    window.scrollTo(0, 0);
    // The same screen again (its link in the navigation): still move focus.
    if (routeOf(location.hash) === route)
      main.current?.focus({ preventScroll: true });
  }
  function openJob(id: string) {
    if (!confirmLeave()) return;
    const [page, query = ""] = location.hash.split("?");
    const params = new URLSearchParams(query);
    params.delete("job");
    params.set("job", id);
    history.pushState(null, "", `${page || "#" + HOME}?${params}`);
    lastRoute.current = location.hash;
    setOverlay({ kind: "job", id });
  }
  function closeObject() {
    if (!confirmLeave()) return;
    const [page, query = ""] = location.hash.split("?");
    const params = new URLSearchParams(query);
    params.delete("job");
    history.replaceState(null, "", `${page}${params.size ? "?" + params : ""}`);
    lastRoute.current = location.hash;
    setOverlay(null);
  }
  // An application opens on its own page, the review page.
  const openApp = (id: string) =>
    navigate(`review?application=${encodeURIComponent(id)}`);
  const nav = {
    route,
    counts: {
      ready: applications.data.ready_count ?? 0,
      questions: questions.data.total,
      inbox: inbox.data.total,
    },
    onNavigate: (id: string) => navigate(id),
  };
  const status = (
    <AgentStatus
      runs={runs.data}
      onOpen={() => navigate("activity?section=runs")}
    />
  );
  return (
    <>
      <a
        className="skip-link"
        href="#content"
        onClick={(event) => {
          // The hash is the route: move focus without changing it.
          event.preventDefault();
          main.current?.focus();
          main.current?.scrollIntoView();
        }}
      >
        Skip to content
      </a>
      <div className="app">
        {!narrow && <Sidebar {...nav} foot={status} />}
        <div className="main">
          <TopBar
            route={route}
            saving={pending}
            onRefresh={refresh}
            theme={theme}
            onTheme={toggleTheme}
            density={density}
            onDensity={toggleDensity}
            inert={more}
          />
          <main
            id="content"
            className="page"
            tabIndex={-1}
            ref={main}
            inert={more}
          >
            {/* The old pages bring their own stylesheet, scoped to .legacy. */}
            <div className={REBUILT.includes(route) ? "screen" : "legacy"}>
              <Screen route={route}>
                {route === "today" ? (
                  <TodayPage onOpenJob={openJob} onOpenApplication={openApp} />
                ) : route === "activity" ? (
                  <ActivityPage
                    openQuestions={questions.data.total}
                    onOpenJob={openJob}
                    onOpenApplication={openApp}
                  />
                ) : route === "inbox" || route === "shortlist" ? (
                  <JobsPage
                    key={route}
                    defaultQueue={route}
                    onAdd={() => setOverlay({ kind: "add" })}
                    onOpen={openJob}
                  />
                ) : route === "applications" ? (
                  <ApplicationsPage />
                ) : route === "review" ? (
                  <ReviewPage onOpenJob={openJob} onOpenApplication={openApp} />
                ) : route === "collection" ? (
                  <CollectionPage />
                ) : route === "career" ? (
                  <CareerPage />
                ) : route === "policy" ? (
                  <PolicyPage />
                ) : route === "templates" ? (
                  <TemplatesPage />
                ) : (
                  <SettingsPage
                    theme={theme}
                    onTheme={toggleTheme}
                    onLogout={() =>
                      onLogout().catch((e) =>
                        notify(
                          e instanceof Error
                            ? e.message
                            : "Unable to sign out.",
                          true,
                        ),
                      )
                    }
                  />
                )}
              </Screen>
            </div>
          </main>
        </div>
        {narrow && (
          <TabBar
            {...nav}
            moreOpen={more}
            moreButton={moreButton}
            onMore={setMore}
          />
        )}
        {narrow && more && (
          <MoreSheet {...nav} foot={status} onClose={() => setMore(false)} />
        )}
      </div>
      <div className="legacy">
        {overlay?.kind === "add" && (
          <OverlayFrame name="The job form">
            <AddJob
              onClose={closeObject}
              onCreated={(id) => navigate("inbox", { kind: "job", id })}
            />
          </OverlayFrame>
        )}
        {overlay?.kind === "job" && (
          <OverlayFrame name="This job">
            <JobDrawer
              key={overlay.id}
              id={overlay.id}
              onClose={closeObject}
              onApplication={openApp}
            />
          </OverlayFrame>
        )}
      </div>
    </>
  );
}
