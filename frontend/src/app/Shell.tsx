import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Building2, HelpCircle, Inbox, Kanban, PlayCircle, Plus, Settings } from "lucide-react";

import { TOKEN_INVALID_EVENT, api, getToken } from "../api/client";
import { Button } from "../components/Button";
import { Kbd } from "../components/Kbd";
import { AddJobDialog } from "../features/shared/AddJobDialog";
import { keys, useStats } from "../features/shared/queries";
import { HelpDialog } from "./HelpDialog";
import { useHotkeys } from "./hotkeys";
import { VIEWS, navigate } from "./router";
import type { View } from "./router";
import { TokenDialog } from "./TokenDialog";

const ICONS: Record<View, typeof Inbox> = {
  inbox: Inbox,
  pipeline: Kanban,
  companies: Building2,
  runs: PlayCircle,
  system: Settings,
};

export function Shell({ view, children }: { view: View; children: ReactNode }) {
  const [help, setHelp] = useState(false);
  const [adding, setAdding] = useState(false);
  const [tokenPrompt, setTokenPrompt] = useState(false);
  const [tokenDismissed, setTokenDismissed] = useState(false);
  const auth = useQuery({ queryKey: keys.auth, queryFn: api.dashboardAuth });
  const stats = useStats();
  const tokenMissing = Boolean(auth.data?.token_required) && !getToken() && !tokenDismissed;

  useEffect(() => {
    const onInvalid = () => setTokenPrompt(true);
    window.addEventListener(TOKEN_INVALID_EVENT, onInvalid);
    return () => window.removeEventListener(TOKEN_INVALID_EVENT, onInvalid);
  }, []);

  useHotkeys({
    ...Object.fromEntries(
      VIEWS.map((entry) => [entry.key, () => navigate({ view: entry.id, jobId: null })]),
    ),
    "?": () => setHelp((open) => !open),
    n: () => setAdding(true),
  });

  const counts = stats.data?.by_status;

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="flex w-full shrink-0 flex-col border-b border-slate-200 bg-white md:h-screen md:w-56 md:border-b-0 md:border-r">
        <div className="flex items-center justify-between px-4 py-3">
          <a href="?view=inbox" className="text-base font-semibold tracking-tight">
            Openings
          </a>
          <Button
            size="sm"
            variant="ghost"
            aria-label="Keyboard shortcuts"
            onClick={() => setHelp(true)}
          >
            <HelpCircle size={16} />
          </Button>
        </div>
        <nav
          className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:pb-0"
          aria-label="Views"
        >
          {VIEWS.map((entry) => {
            const Icon = ICONS[entry.id];
            const active = entry.id === view;
            const count =
              entry.id === "inbox"
                ? counts?.new
                : entry.id === "pipeline" && counts
                  ? Object.entries(counts)
                      .filter(([status]) => status !== "new")
                      .reduce((sum, [, value]) => sum + value, 0)
                  : undefined;
            return (
              <a
                key={entry.id}
                href={`?view=${entry.id}`}
                aria-current={active ? "page" : undefined}
                onClick={(event) => {
                  event.preventDefault();
                  navigate({ view: entry.id, jobId: null });
                }}
                className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${
                  active ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100"
                }`}
              >
                <Icon size={16} />
                <span className="flex-1">{entry.label}</span>
                {count !== undefined ? (
                  <span
                    className={`text-xs tabular-nums ${active ? "text-slate-300" : "text-slate-500"}`}
                  >
                    {count}
                  </span>
                ) : null}
                <span className="hidden md:inline">
                  <Kbd>{entry.key}</Kbd>
                </span>
              </a>
            );
          })}
        </nav>
        <div className="mt-auto hidden px-3 py-3 md:block">
          <Button
            variant="primary"
            className="w-full justify-center"
            onClick={() => setAdding(true)}
          >
            <Plus size={14} /> Add posting
          </Button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-4 md:overflow-y-auto md:p-6">{children}</main>

      <HelpDialog open={help} onClose={() => setHelp(false)} />
      <AddJobDialog open={adding} onClose={() => setAdding(false)} />
      <TokenDialog
        open={tokenPrompt || tokenMissing}
        onClose={() => {
          setTokenPrompt(false);
          setTokenDismissed(true);
        }}
      />
    </div>
  );
}
