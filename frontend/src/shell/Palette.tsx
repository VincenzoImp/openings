import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import {
  Briefcase,
  Keyboard,
  LogOut,
  Monitor,
  Moon,
  Plus,
  Search,
  Send,
  Sun,
} from "lucide-react";
import { usePaletteSearch } from "../data/shell";
import { Kbd } from "../ui/Button";
import { Icon, type LucideIcon } from "../ui/Icon";
import type { ThemeMode } from "../ui/theme";
import { NAV_ITEMS } from "./nav";
import { href, navigate } from "./router";

/** The value, once it stopped changing for `ms`. */
function useSettled<T>(value: T, ms: number) {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

interface Command {
  id: string;
  label: string;
  sub?: string;
  icon: LucideIcon;
  kbd?: string;
  run: () => void;
}
interface Group {
  label: string;
  items: Command[];
}

/** The ⌘K palette: jobs and applications by title or company, and commands. */
export function Palette({
  open,
  onClose,
  onAddJob,
  onShortcuts,
  onTheme,
  onSignOut,
}: {
  open: boolean;
  onClose: () => void;
  onAddJob: () => void;
  onShortcuts: () => void;
  onTheme: (mode: ThemeMode) => void;
  onSignOut: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const returnTo = useRef<HTMLElement | null>(null);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const id = useId();
  const search = usePaletteSearch(useSettled(q.trim(), 150));

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) {
      returnTo.current = document.activeElement as HTMLElement | null;
      setQ("");
      setActive(0);
      element.showModal();
      input.current?.focus();
    } else if (!open && element.open) element.close();
  }, [open]);

  const groups = useMemo<Group[]>(() => {
    const term = q.trim().toLowerCase();
    const matches = (command: Command) =>
      !term || command.label.toLowerCase().includes(term);
    const jobs: Command[] = search.jobs.map((job) => ({
      id: `job-${job.id}`,
      label: job.title || "Untitled role",
      sub: [job.company, job.location].filter(Boolean).join(" · "),
      icon: Briefcase,
      run: () => navigate(href("jobs", {}, { job: job.id })),
    }));
    const applications: Command[] = search.applications.map((item) => ({
      id: `application-${item.id}`,
      label: item.title,
      sub: item.company,
      icon: Send,
      run: () => navigate(href("application", { id: item.id })),
    }));
    const go: Command[] = NAV_ITEMS.map((item) => ({
      id: `go-${item.id}`,
      label: `Go to ${item.label}`,
      icon: item.icon,
      kbd: item.chord,
      run: () => navigate(href(item.id)),
    })).filter(matches);
    const actions: Command[] = [
      {
        id: "add-job",
        label: "Add a job",
        icon: Plus,
        kbd: "N",
        run: onAddJob,
      },
      {
        id: "theme-system",
        label: "Theme: System",
        icon: Monitor,
        run: () => onTheme("system"),
      },
      {
        id: "theme-light",
        label: "Theme: Light",
        icon: Sun,
        run: () => onTheme("light"),
      },
      {
        id: "theme-dark",
        label: "Theme: Dark",
        icon: Moon,
        run: () => onTheme("dark"),
      },
      {
        id: "shortcuts",
        label: "Keyboard shortcuts",
        icon: Keyboard,
        kbd: "?",
        run: onShortcuts,
      },
      { id: "sign-out", label: "Sign out", icon: LogOut, run: onSignOut },
    ].filter(matches);
    // A command whose name matches comes first, then the records found.
    return [
      { label: "Go to", items: go },
      { label: "Actions", items: actions },
      { label: "Jobs", items: jobs },
      { label: "Applications", items: applications },
    ].filter((group) => group.items.length);
  }, [
    q,
    search.jobs,
    search.applications,
    onAddJob,
    onShortcuts,
    onTheme,
    onSignOut,
  ]);
  const flat = groups.flatMap((group) => group.items);
  const current = Math.min(active, Math.max(flat.length - 1, 0));
  useEffect(() => setActive(0), [q]);
  useEffect(() => {
    document
      .getElementById(`${id}-${current}`)
      ?.scrollIntoView({ block: "nearest" });
  }, [id, current]);

  function run(command: Command | undefined) {
    if (!command) return;
    returnTo.current = null;
    onClose();
    command.run();
  }
  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((current + step + flat.length) % Math.max(flat.length, 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      run(flat[current]);
    }
  }

  let index = -1;
  return (
    <dialog
      ref={dialog}
      className="shell-palette"
      aria-label="Search and commands"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClose={() => {
        const target = returnTo.current;
        returnTo.current = null;
        if (target?.isConnected) target.focus();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      {open && (
        <>
          <div className="shell-palette-field">
            <Icon icon={Search} />
            <input
              ref={input}
              role="combobox"
              aria-label="Search jobs, applications and commands"
              aria-expanded="true"
              aria-controls={`${id}-list`}
              aria-activedescendant={
                flat.length ? `${id}-${current}` : undefined
              }
              aria-autocomplete="list"
              placeholder="Search jobs, applications and commands"
              value={q}
              onChange={(event) => setQ(event.target.value)}
              onKeyDown={onKeyDown}
              autoComplete="off"
              spellCheck={false}
            />
            <Kbd>Esc</Kbd>
          </div>
          <div
            className="shell-palette-list"
            id={`${id}-list`}
            role="listbox"
            aria-label="Results"
          >
            {groups.map((group) => (
              <div role="group" aria-label={group.label} key={group.label}>
                <div className="shell-palette-head" aria-hidden="true">
                  {group.label}
                </div>
                {group.items.map((command) => {
                  index += 1;
                  const mine = index;
                  return (
                    <div
                      key={command.id}
                      id={`${id}-${mine}`}
                      role="option"
                      aria-selected={mine === current}
                      className="shell-palette-item"
                      onMouseMove={() => setActive(mine)}
                      onClick={() => run(command)}
                    >
                      <Icon icon={command.icon} />
                      <span className="shell-palette-label">
                        {command.label}
                        {command.sub && (
                          <span className="shell-palette-sub">
                            {command.sub}
                          </span>
                        )}
                      </span>
                      {command.kbd && <Kbd>{command.kbd}</Kbd>}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
          <p className="shell-palette-empty" role="status">
            {flat.length
              ? ""
              : search.loading
                ? "Searching…"
                : `Nothing matches “${q}”.`}
          </p>
        </>
      )}
    </dialog>
  );
}
