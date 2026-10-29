import { useEffect, useState, type FormEvent } from "react";
import {
  api,
  setCsrf,
  type ListResult,
  type Profile,
  type Session,
} from "./api";
import { useResource, useWorkspace } from "./state";
import { Button, ErrorBox, Icon, Loading, type IconName } from "./ui";
import OverviewPage from "./pages/Overview";
import { AddJob, JobDrawer, JobsPage } from "./pages/Jobs";
import { ApplicationDrawer, ApplicationsPage } from "./pages/Applications";
import CompaniesPage from "./pages/Companies";
import CareerPage from "./pages/Career";
import TemplatesPage from "./pages/Templates";
import SettingsPage from "./pages/Settings";
const pages: { id: string; title: string; icon: IconName }[] = [
  { id: "overview", title: "Overview", icon: "overview" },
  { id: "inbox", title: "Inbox", icon: "inbox" },
  { id: "applications", title: "Applications", icon: "applications" },
  { id: "companies", title: "Companies", icon: "companies" },
  { id: "career", title: "Career", icon: "career" },
  { id: "templates", title: "Templates", icon: "templates" },
  { id: "settings", title: "Settings", icon: "settings" },
];
type Overlay =
  { kind: "add" } | { kind: "job" | "application"; id: string } | null;
function readRoute() {
  const hash = location.hash.slice(1).split("?")[0];
  return pages.some((p) => p.id === hash) ? hash : "overview";
}
export default function App() {
  const [session, setSession] = useState<Session | null>(null),
    [error, setError] = useState<string | null>(null);
  async function bootstrap() {
    try {
      setError(null);
      const result = await api<Session>("/auth/session");
      setCsrf(result.csrf_token || "");
      setSession(result);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to reach your workspace.",
      );
    }
  }
  useEffect(() => {
    void bootstrap();
    const expired = () => {
      setCsrf("");
      setSession({ configured: true, authenticated: false });
    };
    window.addEventListener("openings:unauthorized", expired);
    return () => window.removeEventListener("openings:unauthorized", expired);
  }, []);
  if (error)
    return (
      <div className="auth-shell">
        <div className="auth-card">
          <Brand />
          <h1>Your workspace is taking a moment.</h1>
          <ErrorBox message={error} retry={bootstrap} />
        </div>
      </div>
    );
  if (!session)
    return (
      <div className="auth-shell">
        <Loading />
      </div>
    );
  if (!session.authenticated)
    return (
      <Auth
        configured={session.configured}
        onSuccess={(value) => {
          setCsrf(value.csrf_token || "");
          setSession(value);
        }}
      />
    );
  return (
    <Shell
      onLogout={async () => {
        await api("/auth/logout", "POST");
        await bootstrap();
      }}
    />
  );
}
function Brand() {
  return (
    <span className="brand">
      <span className="brandmark" aria-hidden="true" />
      <span className="brandname">Openings</span>
    </span>
  );
}
function Auth({
  configured,
  onSuccess,
}: {
  configured: boolean;
  onSuccess: (session: Session) => void;
}) {
  const [error, setError] = useState<string | null>(null),
    [pending, setPending] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const f = new FormData(e.currentTarget),
      password = String(f.get("password") || "");
    if (!configured && password !== f.get("confirm")) {
      setError("The passwords do not match.");
      return;
    }
    setPending(true);
    try {
      onSuccess(
        await api<Session>(configured ? "/auth/login" : "/auth/setup", "POST", {
          password,
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to sign in.");
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="auth-shell">
      <section className="auth-card">
        <Brand />
        <div className="eyebrow">Your job search workspace</div>
        <h1>{configured ? "Welcome back." : "Room for your next chapter."}</h1>
        <p>
          {configured
            ? "Sign in to your private workspace."
            : "Create the owner password for this installation. Your profile, jobs and documents stay together in one workspace."}
        </p>
        {error && <ErrorBox message={error} />}
        <form onSubmit={submit}>
          <label className="field">
            <span>{configured ? "Password" : "Choose a password"}</span>
            <input
              name="password"
              type="password"
              minLength={configured ? 1 : 10}
              required
              autoFocus
              autoComplete={configured ? "current-password" : "new-password"}
            />
            {!configured && <small>At least 10 characters.</small>}
          </label>
          {!configured && (
            <label className="field">
              <span>Confirm password</span>
              <input
                name="confirm"
                type="password"
                minLength={10}
                required
                autoComplete="new-password"
              />
            </label>
          )}
          <Button variant="primary" disabled={pending}>
            {pending
              ? "One moment…"
              : configured
                ? "Sign in"
                : "Create workspace"}
          </Button>
        </form>
        <footer>
          Knowledge, opportunities and the work you put into them.
        </footer>
      </section>
    </div>
  );
}
function Shell({ onLogout }: { onLogout: () => Promise<void> }) {
  const [route, setRoute] = useState(readRoute),
    [mobile, setMobile] = useState(false),
    [overlay, setOverlay] = useState<Overlay>(null),
    [theme, setTheme] = useState(() => {
      try {
        return (
          localStorage.getItem("openings-theme") ||
          (matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light")
        );
      } catch {
        return "light";
      }
    });
  const { pending, refresh, notify } = useWorkspace();
  const profile = useResource<Partial<Profile>>("/career/profile", {}),
    inbox = useResource<ListResult<never>>("/jobs?triage=inbox&limit=1", {
      items: [],
      total: 0,
    });
  useEffect(() => {
    const listener = () => {
      setRoute(readRoute());
      setOverlay(null);
      setMobile(false);
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", listener);
    window.addEventListener("popstate", listener);
    return () => {
      window.removeEventListener("hashchange", listener);
      window.removeEventListener("popstate", listener);
    };
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("openings-theme", theme);
    } catch {}
  }, [theme]);
  useEffect(() => {
    document.title = `${pages.find((p) => p.id === route)?.title || "Workspace"} · Openings`;
  }, [route]);
  useEffect(() => {
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobile(false);
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, []);
  function navigate(id: string, next: Overlay = null) {
    history.pushState(null, "", `#${id}`);
    setRoute(id);
    setOverlay(next);
    setMobile(false);
    window.scrollTo(0, 0);
  }
  function openJob(id: string) {
    setOverlay({ kind: "job", id });
  }
  function openApp(id: string) {
    setOverlay({ kind: "application", id });
  }
  const toggleTheme = () => setTheme((t) => (t === "light" ? "dark" : "light"));
  const name = profile.data.name || "Your workspace";
  return (
    <>
      <div className="app-shell">
        <button
          className={`mobile-shade ${mobile ? "open" : ""}`}
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
          tabIndex={-1}
        />
        <aside className={`sidebar ${mobile ? "open" : ""}`}>
          <a
            href="#overview"
            className="brand"
            aria-label="Openings overview"
            onClick={(e) => {
              e.preventDefault();
              navigate("overview");
            }}
          >
            <span className="brandmark" aria-hidden="true" />
            <span className="brandname">Openings</span>
          </a>
          <div className="workspace-label">Personal workspace</div>
          <nav className="nav" aria-label="Main navigation">
            {pages.map((page) => (
              <a
                href={`#${page.id}`}
                className={route === page.id ? "active" : ""}
                aria-current={route === page.id ? "page" : undefined}
                key={page.id}
                onClick={(e) => {
                  e.preventDefault();
                  navigate(page.id);
                }}
              >
                <Icon name={page.icon} />
                {page.title}
                {page.id === "inbox" && (
                  <span className="navcount">{inbox.data.total}</span>
                )}
              </a>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="sidebar-note">
              <b>Your search, in one place.</b>
              <br />
              Knowledge, opportunities and the work you put into them.
            </div>
            <div className="user">
              <span className="avatar">
                {name
                  .split(" ")
                  .slice(0, 2)
                  .map((x) => x[0])
                  .join("")
                  .toUpperCase()}
              </span>
              <div className="usercopy">
                <strong>{name}</strong>
                <br />
                <span className="muted">Personal workspace</span>
              </div>
              <button
                className="iconbtn"
                aria-label="Toggle color theme"
                onClick={toggleTheme}
              >
                <Icon name={theme === "light" ? "moon" : "sun"} />
              </button>
            </div>
          </div>
        </aside>
        <main className="main">
          <div className="topbar">
            <div className="breadcrumb">
              <button
                className="iconbtn mobile-menu"
                aria-label="Open navigation"
                aria-expanded={mobile}
                onClick={() => setMobile(true)}
              >
                <Icon name="menu" />
              </button>
              <span>Workspace</span>
              <span>/</span>
              {pages.find((p) => p.id === route)?.title}
            </div>
            <div className="topbar-right">
              {pending && (
                <span className="saving" role="status">
                  <span className="spinner" />
                  Saving…
                </span>
              )}
              <button
                className="iconbtn"
                aria-label="Refresh workspace"
                onClick={refresh}
              >
                <Icon name="refresh" />
              </button>
            </div>
          </div>
          <div className="content">
            {route === "overview" ? (
              <OverviewPage
                onAdd={() => setOverlay({ kind: "add" })}
                onNavigate={navigate}
              />
            ) : route === "inbox" ? (
              <JobsPage
                onAdd={() => setOverlay({ kind: "add" })}
                onOpen={openJob}
              />
            ) : route === "applications" ? (
              <ApplicationsPage onOpen={openApp} />
            ) : route === "companies" ? (
              <CompaniesPage />
            ) : route === "career" ? (
              <CareerPage />
            ) : route === "templates" ? (
              <TemplatesPage />
            ) : (
              <SettingsPage
                theme={theme}
                onTheme={toggleTheme}
                onLogout={() =>
                  onLogout().catch((e) =>
                    notify(
                      e instanceof Error ? e.message : "Unable to sign out.",
                      true,
                    ),
                  )
                }
              />
            )}
          </div>
        </main>
      </div>
      {overlay?.kind === "add" && (
        <AddJob
          onClose={() => setOverlay(null)}
          onCreated={(id) => navigate("inbox", { kind: "job", id })}
        />
      )}{" "}
      {overlay?.kind === "job" && (
        <JobDrawer
          id={overlay.id}
          onClose={() => setOverlay(null)}
          onApplication={(id) =>
            navigate("applications", { kind: "application", id })
          }
        />
      )}{" "}
      {overlay?.kind === "application" && (
        <ApplicationDrawer id={overlay.id} onClose={() => setOverlay(null)} />
      )}
    </>
  );
}
