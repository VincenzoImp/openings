import type { CSSProperties } from "react";
import { ErrorBanner, Tabs } from "../design";
import { PageHead } from "../library/common";
import { useFresh } from "../library/useFresh";
import { useShell } from "../shell/context";
import { useUrlState } from "../state";
import { Backup } from "./settings/Backup";
import { Connect } from "./settings/Connect";
import { TWO_UP, type WorkspaceInfo } from "./settings/model";
import { Skills } from "./settings/Skills";
import { CreateToken, Tokens } from "./settings/Tokens";
import { Workspace } from "./settings/Workspace";

const TABS = [
  { id: "agents", label: "Agent access" },
  { id: "skills", label: "Skills" },
  { id: "backup", label: "Backup and restore" },
  { id: "workspace", label: "Workspace" },
];
const tabOf = (value: string) =>
  TABS.some((tab) => tab.id === value) ? value : "agents";

/**
 * Who may operate this workspace, how the agent works in it and how the data
 * is kept. Parts that need owner authority are marked Owner only: an agent
 * token is refused there over REST and MCP alike.
 */
export default function SettingsPage() {
  const { signOut: onLogout } = useShell();
  const [raw] = useUrlState("section", "agents");
  const section = tabOf(raw);
  const info = useFresh<WorkspaceInfo>("/workspace", {}, ["backup"]);
  const show = (next: string) => {
    history.replaceState(
      null,
      "",
      next === "agents" ? "#settings" : `#settings?section=${next}`,
    );
    window.dispatchEvent(new PopStateEvent("popstate"));
  };
  return (
    <>
      <PageHead title="Settings">
        Who may operate this workspace, how your agent works in it, and how the
        data is kept.
      </PageHead>
      {info.error && <ErrorBanner message={info.error} retry={info.reload} />}
      <Tabs
        id="settings"
        label="Settings sections"
        value={section}
        onChange={show}
        items={TABS}
      >
        {section === "skills" ? (
          <Skills release={info.data.version} />
        ) : section === "backup" ? (
          <Backup storage={info.data.storage} />
        ) : section === "workspace" ? (
          <Workspace info={info.data} onLogout={onLogout} />
        ) : (
          <div className="stack">
            <Tokens />
            <div
              className="split"
              style={{ "--split": TWO_UP } as CSSProperties}
            >
              <CreateToken />
              <Connect origin={info.data.origin || location.origin} />
            </div>
          </div>
        )}
      </Tabs>
    </>
  );
}
