import { MoreHorizontal, Reply, Send } from "lucide-react";
import { ToneText } from "../../ui/Badge";
import { IconButton } from "../../ui/Button";
import { StatusGlyph, STAGES } from "../../ui/Icon";
import { ListRow, type RowAction } from "../../ui/List";
import { Menu, type MenuEntry } from "../../ui/Menu";
import { href, navigate } from "../../shell/router";
import { jobOf, type ApplicationRow } from "./data";
import type { DialogKind } from "./dialogs";
import { isSent, stageOf, statusPhrase } from "./model";
import { HighPriority } from "./priority";

/** The page of an application. */
export const pageHref = (id: string) => href("application", { id });

/**
 * Priority as a leading glyph: four bars, as many filled as it is high
 * (1 fills four, 5 none). Neutral: priority orders, it does not alarm.
 */
export function PriorityGlyph({ priority }: { priority?: number | null }) {
  if (!priority) return null;
  const filled = 5 - priority;
  return (
    <svg
      className="ap-priority"
      viewBox="0 0 14 14"
      width="14"
      height="14"
      role="img"
      aria-label={`Priority ${priority}`}
    >
      {[0, 1, 2, 3].map((bar) => (
        <rect
          key={bar}
          x={1 + bar * 3.25}
          y={10 - bar * 2.5}
          width="2.25"
          height={3 + bar * 2.5}
          rx="0.6"
          data-on={bar < filled || undefined}
        />
      ))}
    </svg>
  );
}

/** The stage glyph and the one status phrase of an application. */
export function StatusText({
  app,
  noReplyDays,
}: {
  app: ApplicationRow;
  noReplyDays: number;
}) {
  const stage = stageOf(app);
  const phrase = statusPhrase(app, noReplyDays);
  return (
    <span className="ap-status">
      <StatusGlyph stage={stage} />
      <span className="ui-sr">{STAGES[stage]}: </span>
      <ToneText tone={phrase.tone}>{phrase.text}</ToneText>
    </span>
  );
}

/** The `…` entries of an application, by its stage. */
export function rowMenu(
  app: Pick<ApplicationRow, "status">,
  open: (kind: DialogKind) => void,
  reopen: () => void,
): MenuEntry[] {
  return [
    { id: "stage", label: "Change stage…", onSelect: () => open("stage") },
    app.status === "closed"
      ? { id: "reopen", label: "Reopen", onSelect: reopen }
      : { id: "close", label: "Close…", onSelect: () => open("close") },
    "separator",
    {
      id: "delete",
      label: "Delete permanently…",
      danger: true,
      onSelect: () => open("delete"),
    },
  ];
}

/**
 * One application: role, company and place, then its one status phrase. The
 * stage glyph shows only where stages mix (`mixed`); in a stage tab or group
 * the phrase says the rest (a Ready row: its deadline). On hover, focus or
 * selection the phrase gives way to the stage's action (Apply, Record reply)
 * and the `…` menu.
 */
export function ApplicationRowView({
  app,
  noReplyDays,
  mixed = true,
  onDialog,
  onReopen,
}: {
  app: ApplicationRow;
  noReplyDays: number;
  /** Rows of several stages together: the stage glyph tells them apart. */
  mixed?: boolean;
  onDialog: (kind: DialogKind) => void;
  onReopen: () => void;
}) {
  const job = jobOf(app);
  const stage = stageOf(app);
  const phrase = statusPhrase(app, noReplyDays, undefined, {
    stageShown: !mixed,
  });
  const actions: RowAction[] = [];
  if (stage === "ready")
    actions.push({
      label: "Apply",
      icon: Send,
      onClick: () => navigate(pageHref(app.id)),
    });
  if (isSent(app.status))
    actions.push({
      label: "Record reply",
      icon: Reply,
      shortcut: "R",
      onClick: () => onDialog("reply"),
    });
  return (
    <ListRow
      id={app.id}
      href={pageHref(app.id)}
      leading={<HighPriority priority={app.priority} />}
      title={job.title}
      sub={
        <>
          {job.company}
          {job.location && (
            <span className="ap-sub-place">
              {job.company ? " · " : ""}
              {job.location}
            </span>
          )}
          {phrase.text && (
            <span className="ap-sub-status">
              {" · "}
              <ToneText tone={phrase.tone}>{phrase.text}</ToneText>
            </span>
          )}
        </>
      }
      meta={
        mixed ? (
          <StatusText app={app} noReplyDays={noReplyDays} />
        ) : (
          phrase.text && (
            <span className="ap-status">
              <span className="ui-sr">{STAGES[stage]}: </span>
              <ToneText tone={phrase.tone}>{phrase.text}</ToneText>
            </span>
          )
        )
      }
      actions={actions}
      menu={(tabIndex) => (
        <Menu
          label={`Actions for ${job.title}`}
          placement="bottom-end"
          items={rowMenu(app, onDialog, onReopen)}
          trigger={(props) => (
            <IconButton
              {...props}
              icon={MoreHorizontal}
              label="More actions"
              size="sm"
              raised
              tabIndex={tabIndex}
              tooltip="none"
            />
          )}
        />
      )}
    />
  );
}
