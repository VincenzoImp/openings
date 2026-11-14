import type { JSX } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Database,
  KeyRound,
  UserRound,
  Wrench,
} from "lucide-react";
import { href, useRoute } from "../../shell/router";
import { Icon } from "../../ui/Icon";
import { PageHeader } from "../../ui/Page";
import { Account } from "./Account";
import { Advanced } from "./Advanced";
import { Agents } from "./Agents";
import { Data } from "./Data";
import { SECTIONS, sectionOf, type SectionId } from "./model";
import "./settings.css";

const ICONS = {
  account: UserRound,
  agents: KeyRound,
  data: Database,
  advanced: Wrench,
};
const BODIES: Record<SectionId, () => JSX.Element> = {
  account: Account,
  agents: Agents,
  data: Data,
  advanced: Advanced,
};

/**
 * Settings, one page: Account, API & agents, Data and Advanced. On a wide
 * screen a sub-navigation sits on the left and Account opens first; on a
 * phone the sections are a list, and one opens as its own page.
 */
export default function SettingsScreen() {
  const route = useRoute();
  const picked = sectionOf(route.query.get("section"));
  const section = picked ?? "account";
  const Body = BODIES[section];
  return (
    <div className="set-screen">
      <PageHeader title="Settings" />
      <div className="set" data-picked={picked ? "" : undefined}>
        <nav className="set-nav" aria-label="Settings sections">
          <ul>
            {SECTIONS.map((item) => (
              <li key={item.id}>
                <a
                  href={href("settings", {}, { section: item.id })}
                  aria-current={item.id === section ? "page" : undefined}
                >
                  <Icon icon={ICONS[item.id]} />
                  <span>{item.label}</span>
                  <Icon icon={ChevronRight} className="set-nav-chevron" />
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="set-body">
          <a className="set-back" href={href("settings")}>
            <Icon icon={ChevronLeft} />
            All settings
          </a>
          <Body key={section} />
        </div>
      </div>
    </div>
  );
}
