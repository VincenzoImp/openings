import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { Button, Card, CardContent, Input } from "@heroui/react";
import { BarChart3, BriefcaseBusiness, Database } from "lucide-react";
import { useState } from "react";

import { getDashboardAuthStatus, getDashboardToken, setDashboardToken } from "./api/client";
import { AnalyticsPage } from "./features/analytics/AnalyticsPage";
import { DatabasePage } from "./features/database/DatabasePage";
import { JobsPage } from "./features/jobs/JobsPage";
import "./styles.css";

type View = "jobs" | "analytics" | "database";

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
  const [view, setView] = useState<View>("jobs");

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950 md:grid md:grid-cols-[260px_minmax(0,1fr)]">
      <aside className="border-b border-slate-200 bg-white p-4 md:min-h-screen md:border-b-0 md:border-r">
        <div className="flex min-h-14 items-center gap-3">
          <span className="grid size-10 place-items-center rounded-lg bg-emerald-700 text-sm font-bold text-white">
            JS
          </span>
          <div>
            <h1 className="text-lg font-semibold leading-tight">Job Search</h1>
            <p className="text-xs text-slate-500">Pipeline Console</p>
          </div>
        </div>

        <nav className="mt-6 grid gap-2 sm:grid-cols-3 md:grid-cols-1" aria-label="Primary">
          <Button
            className="justify-start"
            fullWidth
            onPress={() => setView("jobs")}
            variant={view === "jobs" ? "secondary" : "ghost"}
          >
            <BriefcaseBusiness aria-hidden="true" size={18} />
            Jobs
          </Button>
          <Button
            className="justify-start"
            fullWidth
            onPress={() => setView("analytics")}
            variant={view === "analytics" ? "secondary" : "ghost"}
          >
            <BarChart3 aria-hidden="true" size={18} />
            Analytics
          </Button>
          <Button
            className="justify-start"
            fullWidth
            onPress={() => setView("database")}
            variant={view === "database" ? "secondary" : "ghost"}
          >
            <Database aria-hidden="true" size={18} />
            Database
          </Button>
        </nav>

        {onClearToken ? (
          <Button className="mt-6" fullWidth onPress={onClearToken} variant="outline">
            Reset API token
          </Button>
        ) : null}
      </aside>

      <main className="min-w-0 p-4 md:p-6">
        {view === "jobs" ? <JobsPage /> : null}
        {view === "analytics" ? <AnalyticsPage /> : null}
        {view === "database" ? <DatabasePage /> : null}
      </main>
    </div>
  );
}
