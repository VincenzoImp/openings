import type { CSSProperties } from "react";
import { Banner, Button } from "../../design";
import { dayTime } from "../../library/time";
import { useFresh } from "../../library/useFresh";
import { Connect } from "../settings/Connect";
import { TWO_UP, type WorkspaceInfo } from "../settings/model";
import { CreateToken } from "../settings/Tokens";
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
      <div className="split" style={{ "--split": TWO_UP } as CSSProperties}>
        <CreateToken />
        <Connect origin={info.data.origin || location.origin} />
      </div>
      <p>
        Then tell your agent: <strong>"Set up my Openings workspace."</strong>{" "}
        It reads the setup-openings skill, builds your record and asks you what
        it cannot find.
      </p>
    </div>
  );
}
