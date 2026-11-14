import {
  Building2,
  Copy,
  Ellipsis,
  Pause,
  Pencil,
  Play,
  RefreshCw,
  Rss,
  Search,
  Square,
  Trash2,
} from "lucide-react";
import { IconButton } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import { Menu, type MenuEntry } from "../../ui/Menu";
import {
  countsLine,
  describeSource,
  kindOf,
  sourceStatus,
  type SourceView,
} from "./model";

const KIND_ICONS = { search: Search, company: Building2, feed: Rss };
const KIND_NAMES = {
  search: "Search",
  company: "Company page",
  feed: "Feed",
};

export interface SourceActions {
  edit: (source: SourceView) => void;
  check: (source: SourceView) => void;
  stop: (source: SourceView) => void;
  toggle: (source: SourceView) => void;
  duplicate: (source: SourceView) => void;
  remove: (source: SourceView) => void;
  details: (source: SourceView) => void;
}

/** The `…` menu of a source: Edit, Pause or Resume, Duplicate, Delete. */
export function sourceMenu(
  source: SourceView,
  actions: SourceActions,
): MenuEntry[] {
  const running = sourceStatus(source).running;
  return [
    {
      id: "edit",
      label: "Edit",
      icon: Pencil,
      kbd: "E",
      onSelect: () => actions.edit(source),
    },
    running
      ? {
          id: "stop",
          label: "Stop this check",
          icon: Square,
          onSelect: () => actions.stop(source),
        }
      : {
          id: "check",
          label: "Check now",
          icon: RefreshCw,
          kbd: "C",
          disabled: !source.automatic_collection,
          onSelect: () => actions.check(source),
        },
    {
      id: "toggle",
      label: source.enabled ? "Pause" : "Resume",
      icon: source.enabled ? Pause : Play,
      kbd: "P",
      disabled: !source.automatic_collection,
      onSelect: () => actions.toggle(source),
    },
    {
      id: "duplicate",
      label: "Duplicate",
      icon: Copy,
      onSelect: () => actions.duplicate(source),
    },
    "separator",
    {
      id: "delete",
      label: "Delete permanently…",
      icon: Trash2,
      danger: true,
      onSelect: () => actions.remove(source),
    },
  ];
}

/**
 * One source on three lines: its name, what it searches and where it stands,
 * with the counts of what its jobs became at the end. At rest the row shows
 * only content; on hover or focus Check now and `…` replace the counts. A
 * paused source is greyed; a failing one says so in red, with Details.
 */
export function SourceRow({
  source,
  active,
  labels,
  actions,
  onFocusRow,
}: {
  source: SourceView;
  /** The list's Tab stop. */
  active: boolean;
  labels: Record<string, string>;
  actions: SourceActions;
  onFocusRow: () => void;
}) {
  const kind = kindOf(source);
  const status = sourceStatus(source);
  const counts = countsLine(source.counts);
  const what = describeSource(source, labels);
  const tab = active ? 0 : -1;
  return (
    <li
      className="src-row"
      data-paused={!source.enabled || undefined}
      data-failed={status.failed || undefined}
      onFocus={onFocusRow}
    >
      <span className="src-row-icon" title={KIND_NAMES[kind]}>
        <Icon icon={KIND_ICONS[kind]} />
        <span className="ui-sr">{KIND_NAMES[kind]}: </span>
      </span>
      <button
        type="button"
        className="src-row-open"
        data-row-id={source.id}
        tabIndex={tab}
        aria-describedby={`src-${source.id}-what src-${source.id}-status`}
        onClick={() => actions.edit(source)}
      >
        {source.name}
        {!source.enabled && <span className="src-row-flag"> · Paused</span>}
      </button>
      {what && (
        <span className="src-row-what" id={`src-${source.id}-what`}>
          {what}
        </span>
      )}
      <span className="src-row-status" id={`src-${source.id}-status`}>
        <span className={status.failed ? "src-danger" : undefined}>
          {status.text}
        </span>
        {status.failed && source.automatic_collection && (
          <>
            {" · "}
            <button
              type="button"
              className="src-link"
              tabIndex={tab}
              onClick={() => actions.details(source)}
            >
              Details
            </button>
          </>
        )}
      </span>
      {counts && <span className="src-row-counts">{counts}</span>}
      <span className="src-row-actions">
        {!status.running && source.automatic_collection && (
          <IconButton
            icon={RefreshCw}
            label={`Check ${source.name} now`}
            shortcut="C"
            size="sm"
            raised
            tooltip="above"
            tabIndex={tab}
            onClick={() => actions.check(source)}
          />
        )}
        <Menu
          label={`Actions for ${source.name}`}
          placement="bottom-end"
          items={sourceMenu(source, actions)}
          trigger={(props) => (
            <IconButton
              {...props}
              icon={Ellipsis}
              label={`More actions for ${source.name}`}
              size="sm"
              raised
              tooltip="above"
              tabIndex={tab}
              className="src-row-more"
            />
          )}
        />
      </span>
    </li>
  );
}
