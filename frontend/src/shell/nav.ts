// The navigation: Today · Jobs · Applications | You: Profile · Preferences ·
// Templates | Workspace: Sources · Settings. Only New jobs and Ready
// applications carry a count, the accent "needs you" pill.
import {
  Files,
  House,
  Inbox,
  Radar,
  Send,
  Settings,
  SlidersHorizontal,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import type { RouteId } from "./routes";

export interface NavDef {
  id: RouteId;
  label: string;
  icon: LucideIcon;
  /** Its `g` shortcut, for the palette: "G J". */
  chord?: string;
  needs?: "newJobs" | "readyApplications";
}

export const NAV: { label?: string; items: NavDef[] }[] = [
  {
    items: [
      { id: "today", label: "Today", icon: House, chord: "G T" },
      {
        id: "jobs",
        label: "Jobs",
        icon: Inbox,
        chord: "G J",
        needs: "newJobs",
      },
      {
        id: "applications",
        label: "Applications",
        icon: Send,
        chord: "G A",
        needs: "readyApplications",
      },
    ],
  },
  {
    label: "You",
    items: [
      { id: "profile", label: "Profile", icon: UserRound, chord: "G P" },
      { id: "preferences", label: "Preferences", icon: SlidersHorizontal },
      { id: "templates", label: "Templates", icon: Files },
    ],
  },
  {
    label: "Workspace",
    items: [
      { id: "sources", label: "Sources", icon: Radar },
      { id: "settings", label: "Settings", icon: Settings },
    ],
  },
];

export const NAV_ITEMS = NAV.flatMap((section) => section.items);

/** The phone's bottom bar; the rest is under More. */
export const BOTTOM: RouteId[] = ["today", "jobs", "applications", "profile"];

export const NEEDS_LABEL = {
  newJobs: "new jobs",
  readyApplications: "ready applications",
};
