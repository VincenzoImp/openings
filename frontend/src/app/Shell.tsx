import { useState } from "react";
import type { ReactNode } from "react";
import {
  Building2,
  HelpCircle,
  Inbox,
  Kanban,
  Moon,
  PlayCircle,
  Plus,
  Settings,
  Sun,
} from "lucide-react";

import { Button } from "../components/Button";
import { Kbd } from "../components/Kbd";
import { AddJobDialog } from "../features/shared/AddJobDialog";
import { useStats } from "../features/shared/queries";
import { useFinePointer } from "../features/shared/useMediaQuery";
import { HelpDialog } from "./HelpDialog";
import { useHotkeys } from "./hotkeys";
import { VIEWS, navigate } from "./router";
import type { View } from "./router";
import { useTheme } from "./theme";
import { TokenDialog } from "./TokenDialog";
import { useAuthGate } from "./useAuthGate";

const ICONS: Record<View, typeof Inbox> = {
  inbox: Inbox,
  pipeline: Kanban,
  companies: Building2,
  runs: PlayCircle,
  system: Settings,
};

function ThemeButton() {
  const theme = useTheme();
  const next = theme.resolved === "dark" ? "light" : "dark";
  return (
    <Button
      size="sm"
      variant="ghost"
      aria-label={`Switch to ${next} theme`}
      title={`Theme: ${theme.preference}`}
      onClick={() => theme.setPreference(next)}
    >
      {theme.resolved === "dark" ? (
        <Sun size={16} aria-hidden="true" />
      ) : (
        <Moon size={16} aria-hidden="true" />
      )}
    </Button>
  );
}

export function Shell({ view, children }: { view: View; children: ReactNode }) {
  const [help, setHelp] = useState(false);
  const [adding, setAdding] = useState(false);
  const gate = useAuthGate();
  const stats = useStats();
  const finePointer = useFinePointer();
  const counts = stats.data?.by_status;

  useHotkeys("global", [
    ...VIEWS.map((entry) => ({
      key: entry.key,
      run: () => navigate({ view: entry.id, jobId: null, params: null }),
    })),
    {
      key: "1",
      run: () => navigate({ view: "inbox", jobId: null, params: null }),
      description: "Inbox, Pipeline, Companies, Runs, System",
      group: "Everywhere",
      label: "1 … 5",
    },
    {
      key: "n",
      run: () => setAdding(true),
      description: "Add a posting by hand",
      group: "Everywhere",
    },
    {
      key: "?",
      run: () => setHelp((open) => !open),
      description: "Keyboard shortcuts",
      group: "Everywhere",
    },
  ]);

  const countFor = (id: View): number | undefined => {
    if (!counts) {
      return undefined;
    }
    if (id === "inbox") {
      return counts.new;
    }
    if (id === "pipeline") {
      return (["shortlisted", "applied", "interviewing", "offer"] as const).reduce(
        (sum, status) => sum + (counts[status] ?? 0),
        0,
      );
    }
    return undefined;
  };

  const go = (id: View) => navigate({ view: id, jobId: null, params: null });

  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-edge bg-surface px-3 py-2 md:hidden">
        <a
          href="?view=inbox"
          onClick={(event) => {
            event.preventDefault();
            go("inbox");
          }}
          className="text-base font-semibold tracking-tight"
        >
          Openings
        </a>
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            aria-label="Add posting"
            onClick={() => setAdding(true)}
          >
            <Plus size={16} aria-hidden="true" />
          </Button>
          <ThemeButton />
          <Button size="sm" variant="ghost" aria-label="Help" onClick={() => setHelp(true)}>
            <HelpCircle size={16} aria-hidden="true" />
          </Button>
        </div>
      </header>

      <aside className="hidden w-56 shrink-0 flex-col border-r border-edge bg-surface md:sticky md:top-0 md:flex md:h-dvh">
        <div className="flex items-center justify-between px-4 py-3">
          <a
            href="?view=inbox"
            onClick={(event) => {
              event.preventDefault();
              go("inbox");
            }}
            className="text-base font-semibold tracking-tight"
          >
            Openings
          </a>
          <div className="flex items-center">
            <ThemeButton />
            <Button
              size="sm"
              variant="ghost"
              aria-label="Keyboard shortcuts"
              onClick={() => setHelp(true)}
            >
              <HelpCircle size={16} aria-hidden="true" />
            </Button>
          </div>
        </div>
        <nav className="flex flex-col gap-1 px-2" aria-label="Views">
          {VIEWS.map((entry) => {
            const Icon = ICONS[entry.id];
            const active = entry.id === view;
            const count = countFor(entry.id);
            return (
              <a
                key={entry.id}
                href={`?view=${entry.id}`}
                aria-current={active ? "page" : undefined}
                onClick={(event) => {
                  event.preventDefault();
                  go(entry.id);
                }}
                className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${
                  active ? "bg-fg text-bg" : "text-fg-muted hover:bg-surface-2 hover:text-fg"
                }`}
              >
                <Icon size={16} aria-hidden="true" />
                <span className="flex-1">{entry.label}</span>
                {count !== undefined ? (
                  <span className={`tabular text-xs ${active ? "opacity-70" : "text-fg-faint"}`}>
                    {count}
                  </span>
                ) : null}
                {finePointer ? <Kbd>{entry.key}</Kbd> : null}
              </a>
            );
          })}
        </nav>
        <div className="mt-auto px-3 py-3">
          <Button
            variant="primary"
            className="w-full justify-center"
            onClick={() => setAdding(true)}
          >
            <Plus size={14} aria-hidden="true" /> Add posting
          </Button>
        </div>
      </aside>

      <main className="min-w-0 flex-1 p-4 pb-[calc(4rem+env(safe-area-inset-bottom))] md:overflow-y-auto md:p-6 md:pb-6">
        {children}
      </main>

      <nav
        className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 border-t border-edge bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
        aria-label="Views"
      >
        {VIEWS.map((entry) => {
          const Icon = ICONS[entry.id];
          const active = entry.id === view;
          const count = countFor(entry.id);
          return (
            <a
              key={entry.id}
              href={`?view=${entry.id}`}
              aria-current={active ? "page" : undefined}
              onClick={(event) => {
                event.preventDefault();
                go(entry.id);
              }}
              className={`relative flex flex-col items-center gap-0.5 py-2 text-[11px] ${active ? "text-fg" : "text-fg-muted"}`}
            >
              <Icon size={18} aria-hidden="true" />
              <span>{entry.label}</span>
              {count ? (
                <span className="tabular absolute right-2 top-1 rounded-full bg-accent px-1 text-[10px] font-medium text-on-accent">
                  {count}
                </span>
              ) : null}
            </a>
          );
        })}
      </nav>

      <HelpDialog open={help} onClose={() => setHelp(false)} />
      <AddJobDialog open={adding} onClose={() => setAdding(false)} />
      <TokenDialog open={gate.open} onClose={gate.close} />
    </div>
  );
}
