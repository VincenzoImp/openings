import { useState } from "react";
import { Banner, Button } from "../../design";
import { dayTime } from "../../library/time";
import { useFresh } from "../../library/useFresh";
import { ConnectSnippet, NewTokenDialog } from "../settings/Agents";
import type { WorkspaceInfo } from "../settings/model";
import { connection, type SetupToken } from "./model";

/**
 * Connecting the agent: an agent token, the client configuration of Settings,
 * Agent access, and whether the agent has called yet.
 */
export function ConnectStep({
  tokens,
  onContinue,
}: {
  tokens: SetupToken[];
  onContinue: () => void;
}) {
  const info = useFresh<WorkspaceInfo>("/workspace", {}, []);
  const [creating, setCreating] = useState(false);
  const link = connection(tokens);
  return (
    <div className="stack">
      {link.state === "done" ? (
        <Banner
          tone="info"
          role="status"
          title="Connected."
          action={
            <Button size="sm" onClick={onContinue}>
              Continue
            </Button>
          }
        >
          {link.token!.name} last called {dayTime(link.token!.last_used_at)}.
        </Banner>
      ) : link.state === "waiting" ? (
        <Banner tone="info" role="status">
          <span className="pulse" aria-hidden="true" />
          <strong>Waiting for your agent's first call…</strong> This page
          updates by itself. {link.token!.name} has not been used yet.
        </Banner>
      ) : (
        <p>
          Create an <strong>agent token</strong> and give it to your agent with
          the configuration below. An agent token works in the workspace but
          cannot change your password, manage tokens or restore a backup.
        </p>
      )}
      <div className="row">
        <Button onClick={() => setCreating(true)}>Create an agent token</Button>
      </div>
      <NewTokenDialog open={creating} onClose={() => setCreating(false)} />
      <ConnectSnippet origin={info.data.origin || location.origin} />
      <p>
        Then tell your agent: <strong>"Set up my Openings workspace."</strong>{" "}
        It reads the setup-openings skill, builds your record and asks you what
        it cannot find.
      </p>
    </div>
  );
}
