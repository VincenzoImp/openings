import {
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Plus, Search } from "lucide-react";
import { useAccountName, useNeedsCounts } from "../query/shell";
import { confirmLeave, useFormProtection } from "../state";
// The design system's modules, not its index: the first screen loads only
// the primitives the shell draws (each module brings its own stylesheet).
import { IconButton } from "../ui/Button";
import { isModKey, plainKey } from "../ui/keys";
import {
  AppFrame,
  BottomBar,
  MobileTopBar,
  Sidebar,
  moreMenu,
  type Account,
  type NavItem,
} from "../ui/Shell";
import { ToastProvider } from "../ui/Toast";
import { ShellContext, type ShellApi } from "./context";
import { BOTTOM, NAV, NEEDS_LABEL, type NavDef } from "./nav";
import { addLeaveGuard, href, navigate, useRoute } from "./router";
import { ROUTES } from "./routes";
import { Screen, preload } from "./Screens";
import { markSetup, readNewWorkspace, setupMark } from "./setup";
import { CHORD_MS, readKey, type ShellAction } from "./shortcuts";
import { useTheme } from "./theme";
import "./shell.css";

type Overlay = "palette" | "add" | "help" | null;

// The overlays load when first opened; the first screen stays small.
const Palette = lazy(() =>
  import("./Palette").then((module) => ({ default: module.Palette })),
);
const AddJob = lazy(() =>
  import("./AddJob").then((module) => ({ default: module.AddJob })),
);
const ShortcutSheet = lazy(() =>
  import("./ShortcutSheet").then((module) => ({
    default: module.ShortcutSheet,
  })),
);

/**
 * The application shell: the sidebar on wide screens, the top and bottom
 * bars on phones, the routed screen, the ⌘K palette, the Add job dialog, the
 * shortcut sheet and the global keyboard.
 */
export function Shell({ onSignOut }: { onSignOut: () => void }) {
  useFormProtection();
  const route = useRoute();
  const counts = useNeedsCounts();
  const name = useAccountName();
  const [theme, setTheme] = useTheme();
  const [overlay, setOverlay] = useState<Overlay>(null);
  // Once opened, an overlay stays mounted, so it can close with its exit.
  const [used, setUsed] = useState<Set<Overlay>>(() => new Set());
  useEffect(() => {
    if (overlay && !used.has(overlay))
      setUsed((before) => new Set(before).add(overlay));
  }, [overlay, used]);
  const [title, setTitle] = useState<string | null>(null);
  const [actionsSlot, setActionsSlot] = useState<HTMLElement | null>(null);
  const content = useRef<HTMLElement | null>(null);

  // Unsaved edits of the old screens ask before leaving (#228 replaces this
  // with the screens' own in-app dialog).
  useEffect(() => addLeaveGuard(() => confirmLeave()), []);

  const close = useCallback(() => setOverlay(null), []);
  const shell = useMemo<ShellApi>(
    () => ({
      addJob: () => setOverlay("add"),
      search: () => setOverlay("palette"),
      signOut: onSignOut,
      setTitle,
      actionsSlot,
    }),
    [onSignOut, actionsSlot],
  );

  // The title of the page and of the document.
  const shown = title ?? route.def.title;
  useEffect(() => {
    document.title = `${shown} · Openings`;
  }, [shown]);

  // A new screen starts at the top, with focus on its content, so reading
  // continues there instead of at the top of the navigation.
  const screenKey = `${route.id}:${route.params.id ?? ""}`;
  const previous = useRef(screenKey);
  useEffect(() => {
    if (previous.current === screenKey) return;
    previous.current = screenKey;
    content.current = document.getElementById("content");
    content.current?.scrollTo(0, 0);
    content.current?.focus({ preventScroll: true });
  }, [screenKey]);

  // A workspace nobody has set up opens on the setup guide instead of Today,
  // once per browser (shell/setup.ts), while nothing waits in Jobs.
  const landing = useRef(route.id === "today");
  useEffect(() => {
    if (!landing.current || !counts.loaded) return;
    landing.current = false;
    if (setupMark() || counts.newJobs || counts.readyApplications) return;
    void readNewWorkspace().then((fresh) => {
      if (!fresh) return markSetup("seen");
      markSetup("started");
      if (location.hash.replace(/^#/, "") === "today")
        navigate(href("setup"), { replace: true });
    });
  }, [counts.loaded, counts.newJobs, counts.readyApplications]);

  // The global keyboard. A screen's own keys come first (defaultPrevented);
  // nothing fires while a dialog is open or a field has focus, except ⌘K.
  const pending = useRef<{ key: string; at: number } | null>(null);
  useEffect(() => {
    const run = (action: ShellAction) => {
      if (action.kind === "go") navigate(href(action.route));
      else if (action.kind === "add-job") setOverlay("add");
      else if (action.kind === "search") setOverlay("palette");
      else setOverlay("help");
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "k" && isModKey(event)) {
        event.preventDefault();
        setOverlay((open) => (open === "palette" ? null : "palette"));
        return;
      }
      if (event.defaultPrevented || document.querySelector("dialog[open]"))
        return;
      const key = plainKey(event);
      if (!key) return;
      const chord =
        pending.current && Date.now() - pending.current.at < CHORD_MS
          ? pending.current.key
          : null;
      const next = readKey(key, chord);
      pending.current = next.pending
        ? { key: next.pending, at: Date.now() }
        : null;
      if (!next.action) return;
      event.preventDefault();
      run(next.action);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const account: Account = {
    name,
    theme,
    onTheme: setTheme,
    onShortcuts: () => setOverlay("help"),
    onSignOut,
  };
  const item = (nav: NavDef): NavItem => ({
    id: nav.id,
    label: nav.label,
    icon: nav.icon,
    href: href(nav.id),
    needs: nav.needs ? counts[nav.needs] : undefined,
    needsLabel: nav.needs ? NEEDS_LABEL[nav.needs] : undefined,
  });
  const sections = NAV.map((section) => ({
    label: section.label,
    items: section.items.map(item),
  }));
  const all = sections.flatMap((section) => section.items);
  const bottom = all.filter((nav) => BOTTOM.includes(nav.id as never));
  const rest = all.filter((nav) => !BOTTOM.includes(nav.id as never));
  const parent = route.def.parent ? ROUTES[route.def.parent] : null;

  return (
    <ShellContext.Provider value={shell}>
      <ToastProvider>
        <a
          className="shell-skip"
          href="#content"
          onClick={(event) => {
            // The hash is the route: move focus without changing it.
            event.preventDefault();
            document.getElementById("content")?.focus();
          }}
        >
          Skip to content
        </a>
        <AppFrame
          className="shell"
          sidebar={
            <div
              className="shell-side"
              onPointerOver={(event) => {
                const link = (event.target as HTMLElement).closest("a");
                const id = link?.getAttribute("href")?.slice(1);
                if (id && id in ROUTES) preload(id as keyof typeof ROUTES);
              }}
            >
              <Sidebar
                sections={sections}
                current={route.def.nav}
                onAdd={() => setOverlay("add")}
                onSearch={() => setOverlay("palette")}
                account={account}
              />
            </div>
          }
          topBar={
            <MobileTopBar
              title={shown}
              back={
                parent
                  ? { label: `Back to ${parent.title}`, href: href(parent.id) }
                  : undefined
              }
              actions={
                <>
                  <span className="shell-slot" ref={setActionsSlot} />
                  <span className="shell-defaults">
                    <IconButton
                      icon={Search}
                      label="Search"
                      size="touch"
                      tooltip="none"
                      onClick={() => setOverlay("palette")}
                    />
                    <IconButton
                      icon={Plus}
                      label="Add job"
                      size="touch"
                      tooltip="none"
                      onClick={() => setOverlay("add")}
                    />
                  </span>
                </>
              }
            />
          }
          bottomBar={
            <BottomBar
              items={bottom}
              current={route.def.nav}
              more={moreMenu(rest, account)}
            />
          }
        >
          <Screen key={screenKey} id={route.id} />
        </AppFrame>
        <Suspense fallback={null}>
          {(used.has("palette") || overlay === "palette") && (
            <Palette
              open={overlay === "palette"}
              onClose={close}
              onAddJob={() => setOverlay("add")}
              onShortcuts={() => setOverlay("help")}
              onTheme={setTheme}
              onSignOut={onSignOut}
            />
          )}
          {(used.has("add") || overlay === "add") && (
            <AddJob open={overlay === "add"} onClose={close} />
          )}
          {(used.has("help") || overlay === "help") && (
            <ShortcutSheet open={overlay === "help"} onClose={close} />
          )}
        </Suspense>
      </ToastProvider>
    </ShellContext.Provider>
  );
}
