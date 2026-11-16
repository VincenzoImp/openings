// What the shell offers a screen: its global actions, and the chrome slots a
// screen may fill (the title of the phone's top bar and up to three icon
// buttons beside it). docs/developer/architecture.md (Dashboard) has the
// whole contract of a screen module.
import {
  createContext,
  createElement,
  Fragment,
  useContext,
  useEffect,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

export interface ShellApi {
  /** Open the global Add job dialog. */
  addJob: () => void;
  /** Open the command palette. */
  search: () => void;
  signOut: () => void;
  /** The screen's title for the top bar and the document; null: the route's. */
  setTitle: (title: string | null) => void;
  /** Where TopBarActions draws (the phone's top bar), once it exists. */
  actionsSlot: HTMLElement | null;
}

export const ShellContext = createContext<ShellApi | null>(null);

export function useShell() {
  const shell = useContext(ShellContext);
  if (!shell) throw Error("useShell needs the shell.");
  return shell;
}

/**
 * The screen's title, while it is shown: `useTitle(job.title)` on a page
 * whose route title is generic ("Application").
 */
export function useTitle(title: string | null | undefined) {
  const setTitle = useContext(ShellContext)?.setTitle;
  useEffect(() => {
    setTitle?.(title || null);
  }, [setTitle, title]);
  useEffect(() => () => setTitle?.(null), [setTitle]);
}

/**
 * The phone's top bar: Search first on every screen, then at most two of
 * the screen's own actions as icon buttons, which replace the shell's Add
 * job. A screen whose list has its own search marks that button
 * `data-topbar-search`, and it takes Search's place.
 */
export function TopBarActions({ children }: { children: ReactNode }) {
  const { actionsSlot } = useShell();
  return actionsSlot
    ? createPortal(createElement(Fragment, null, children), actionsSlot)
    : null;
}
