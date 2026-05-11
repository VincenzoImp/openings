import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BarChart3, BriefcaseBusiness, Database } from "lucide-react";
import { useState } from "react";

import { AnalyticsPage } from "./features/analytics/AnalyticsPage";
import { DatabasePage } from "./features/database/DatabasePage";
import { JobsPage } from "./features/jobs/JobsPage";
import "./styles.css";

const queryClient = new QueryClient();

type View = "jobs" | "analytics" | "database";

export default function App() {
  const [view, setView] = useState<View>("jobs");

  return (
    <QueryClientProvider client={queryClient}>
      <div className="app-shell">
        <aside className="sidebar" aria-label="Primary">
          <div className="brand">
            <span className="brand-mark">JS</span>
            <div>
              <h1>Job Search</h1>
              <p>Pipeline Console</p>
            </div>
          </div>

          <nav className="nav">
            <button
              className={view === "jobs" ? "nav-item nav-item--active" : "nav-item"}
              onClick={() => setView("jobs")}
              type="button"
            >
              <BriefcaseBusiness aria-hidden="true" size={18} />
              Jobs
            </button>
            <button
              className={view === "analytics" ? "nav-item nav-item--active" : "nav-item"}
              onClick={() => setView("analytics")}
              type="button"
            >
              <BarChart3 aria-hidden="true" size={18} />
              Analytics
            </button>
            <button
              className={view === "database" ? "nav-item nav-item--active" : "nav-item"}
              onClick={() => setView("database")}
              type="button"
            >
              <Database aria-hidden="true" size={18} />
              Database
            </button>
          </nav>
        </aside>

        <main className="main">
          {view === "jobs" ? <JobsPage /> : null}
          {view === "analytics" ? <AnalyticsPage /> : null}
          {view === "database" ? <DatabasePage /> : null}
        </main>
      </div>
    </QueryClientProvider>
  );
}
