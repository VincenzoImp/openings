import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { Button, Card, CardContent, Input } from "@heroui/react";
import { BarChart3, BriefcaseBusiness, ShieldX, Wrench } from "lucide-react";
import { useEffect, useState } from "react";

import { getDashboardAuthStatus, getDashboardToken, setDashboardToken } from "./api/client";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AnalyticsPage } from "./features/analytics/AnalyticsPage";
import { BlacklistPage } from "./features/blacklist/BlacklistPage";
import { CleanupPage } from "./features/cleanup/CleanupPage";
import { JobsPage } from "./features/jobs/JobsPage";
import "./styles.css";

type View = "jobs" | "blacklist" | "cleanup" | "analytics";

const NAV_ITEMS: {
  icon: typeof BriefcaseBusiness;
  label: string;
  view: View;
}[] = [
  { icon: BriefcaseBusiness, label: "Jobs", view: "jobs" },
  { icon: ShieldX, label: "Blacklist", view: "blacklist" },
  { icon: Wrench, label: "Cleanup", view: "cleanup" },
  { icon: BarChart3, label: "Analytics", view: "analytics" }
];

function viewFromSearch(): View {
  const value = new URLSearchParams(globalThis.location.search).get("view");
  return NAV_ITEMS.some((item) => item.view === value) ? (value as View) : "jobs";
}

export default function App() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: false }
        }
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <DashboardApp />
    </QueryClientProvider>
  );
}

function DashboardApp() {
  const auth = useQuery({
    queryKey: ["dashboard-auth"],
    queryFn: getDashboardAuthStatus,
    staleTime: 60_000
  });
  const [token, setToken] = useState(() => getDashboardToken());

  useEffect(() => {
    const handleInvalidToken = () => setToken(null);
    globalThis.addEventListener("job-search-tool.dashboard-token-invalid", handleInvalidToken);
    return () =>
      globalThis.removeEventListener("job-search-tool.dashboard-token-invalid", handleInvalidToken);
  }, []);

  if (auth.isLoading) {
    return <StatusScreen>Loading dashboard</StatusScreen>;
  }

  if (auth.isError) {
    return <StatusScreen>Unable to load dashboard authentication state</StatusScreen>;
  }

  if (auth.data?.token_required && !token) {
    return (
      <TokenGate
        onSubmit={(nextToken) => {
          setDashboardToken(nextToken);
          setToken(nextToken);
        }}
      />
    );
  }

  return (
    <DashboardShell
      onClearToken={
        auth.data?.token_required
          ? () => {
              setDashboardToken(null);
              setToken(null);
            }
          : undefined
      }
    />
  );
}

function StatusScreen({ children }: { children: string }) {
  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 p-6 text-sm text-slate-600">
      {children}
    </main>
  );
}

function TokenGate({ onSubmit }: { onSubmit: (token: string) => void }) {
  const [value, setValue] = useState("");

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 p-6">
      <Card className="w-full max-w-md border border-slate-200 shadow-sm" variant="default">
        <CardContent className="grid gap-5 p-6">
          <div>
            <h1 className="text-xl font-semibold text-slate-950">API token required</h1>
            <p className="mt-1 text-sm text-slate-600">
              Enter the token configured in JOB_SEARCH_API_TOKEN.
            </p>
          </div>
          <form
            className="grid gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              const token = value.trim();
              if (token) {
                onSubmit(token);
              }
            }}
          >
            <label className="grid gap-1 text-sm font-medium text-slate-700">
              <span>API token</span>
              <Input
                aria-label="API token"
                autoComplete="current-password"
                fullWidth
                onChange={(event) => setValue(event.target.value)}
                type="password"
                value={value}
                variant="secondary"
              />
            </label>
            <Button fullWidth isDisabled={!value.trim()} type="submit" variant="primary">
              Unlock dashboard
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}

function DashboardShell({ onClearToken }: { onClearToken?: () => void }) {
  const [view, setView] = useState<View>(() => viewFromSearch());

  useEffect(() => {
    const handlePopState = () => setView(viewFromSearch());
    globalThis.addEventListener("popstate", handlePopState);
    return () => globalThis.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = (nextView: View) => {
    setView(nextView);
    const params = new URLSearchParams(globalThis.location.search);
    if (nextView === "jobs") {
      params.delete("view");
    } else {
      params.set("view", nextView);
    }
    const nextSearch = params.toString();
    globalThis.history.pushState(null, "", `${globalThis.location.pathname}${nextSearch ? `?${nextSearch}` : ""}`);
  };

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-950 md:grid md:grid-cols-[248px_minmax(0,1fr)]">
      <aside className="border-b border-zinc-200 bg-white p-4 md:min-h-screen md:border-b-0 md:border-r">
        <div className="flex min-h-14 items-center gap-3">
          <span className="grid size-10 place-items-center rounded-md bg-zinc-950 text-sm font-bold text-white">
            JT
          </span>
          <div>
            <h1 className="text-lg font-semibold leading-tight">Job Search</h1>
            <p className="text-xs text-zinc-500">Operations Console</p>
          </div>
        </div>

        <nav className="mt-6 grid gap-2 sm:grid-cols-4 md:grid-cols-1" aria-label="Primary">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <Button
                className="justify-start"
                fullWidth
                key={item.view}
                onPress={() => navigate(item.view)}
                variant={view === item.view ? "secondary" : "ghost"}
              >
                <Icon aria-hidden="true" size={18} />
                {item.label}
              </Button>
            );
          })}
        </nav>

        {onClearToken ? (
          <Button className="mt-6" fullWidth onPress={onClearToken} variant="outline">
            Reset API token
          </Button>
        ) : null}
      </aside>

      <main className="min-w-0 p-4 md:p-6">
        <ErrorBoundary>
          {view === "jobs" ? <JobsPage /> : null}
          {view === "blacklist" ? <BlacklistPage /> : null}
          {view === "cleanup" ? <CleanupPage /> : null}
          {view === "analytics" ? <AnalyticsPage /> : null}
        </ErrorBoundary>
      </main>
    </div>
  );
}
