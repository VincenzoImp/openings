import { useEffect, useRef, type MouseEvent, type RefObject } from "react";
import { Count } from "../design";
import { trappedIndex } from "../design/keys";
import { HOME, NAV, TAB_BAR, destinationOf, type Destination } from "./routes";
import { preloadScreen } from "./Screens";

export interface NavCounts {
  ready: number;
  new: number;
}
interface NavProps {
  route: string;
  counts: NavCounts;
  onNavigate: (route: string) => void;
}

const plural = (n: number, one: string, many: string) =>
  `${n} ${n === 1 ? one : many}`;

function NavCount({ item, counts }: { item: Destination; counts: NavCounts }) {
  if (item.count === "ready" && counts.ready > 0)
    return (
      <Count
        value={counts.ready}
        label={plural(counts.ready, "application", "applications") + " ready"}
      />
    );
  // The review queue informs; it does not ask the owner to act.
  if (item.count === "new")
    return (
      <Count
        value={counts.new}
        quiet
        className="navcount"
        label={plural(counts.new, "new job", "new jobs")}
      />
    );
  return null;
}

function NavLink({
  item,
  route,
  counts,
  onNavigate,
}: NavProps & { item: Destination }) {
  const current = destinationOf(route)?.item === item;
  return (
    <a
      href={`#${item.id}`}
      aria-current={current ? "page" : undefined}
      onPointerEnter={() => preloadScreen(item.id)}
      onFocus={() => preloadScreen(item.id)}
      onClick={(event: MouseEvent) => {
        // Modified clicks keep their browser meaning (new tab, new window).
        if (
          event.button ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        )
          return;
        event.preventDefault();
        onNavigate(item.id);
      }}
    >
      {item.label}
      <NavCount item={item} counts={counts} />
    </a>
  );
}

/** Wide screens: every destination, in its group. */
export function Sidebar(props: NavProps) {
  return (
    <aside className="sidebar">
      <a
        className="brand"
        href={`#${HOME}`}
        onClick={(event) => {
          event.preventDefault();
          props.onNavigate(HOME);
        }}
      >
        Openings
      </a>
      <nav className="nav" aria-label="Main">
        {NAV.map((group) => (
          <div className="nav-group" key={group.group}>
            <span className="eyebrow">{group.group}</span>
            {group.items.map((item) => (
              <NavLink key={item.id} item={item} {...props} />
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}

const flat = NAV.flatMap((group) => group.items);

/** Narrow screens: four destinations and More, which opens the rest. */
export function TabBar({
  moreOpen,
  moreButton,
  onMore,
  ...props
}: NavProps & {
  moreOpen: boolean;
  moreButton: RefObject<HTMLButtonElement | null>;
  onMore: (open: boolean) => void;
}) {
  const current = destinationOf(props.route)?.item.id || "";
  return (
    <nav className="tabbar" aria-label="Main">
      {flat
        .filter((item) => TAB_BAR.includes(item.id))
        .map((item) => (
          <NavLink key={item.id} item={item} {...props} />
        ))}
      <button
        ref={moreButton}
        type="button"
        aria-expanded={moreOpen}
        aria-controls="more-sheet"
        aria-current={
          !current || TAB_BAR.includes(current) ? undefined : "page"
        }
        onClick={() => onMore(!moreOpen)}
      >
        More
      </button>
    </nav>
  );
}

/**
 * The destinations that do not fit in the bottom bar. While it is open, focus
 * stays inside it and Escape (handled by the shell) closes it.
 */
export function MoreSheet({
  onClose,
  ...props
}: NavProps & { onClose: () => void }) {
  const sheet = useRef<HTMLDivElement>(null);
  useEffect(() => {
    sheet.current?.querySelector<HTMLElement>("a")?.focus();
  }, []);
  return (
    <>
      <div className="sheet-shade" onClick={onClose} />
      <div
        ref={sheet}
        id="more-sheet"
        className="more-sheet"
        role="dialog"
        aria-modal="true"
        aria-label="More destinations"
        onKeyDown={(event) => {
          if (event.key !== "Tab") return;
          const targets = Array.from(
            sheet.current?.querySelectorAll<HTMLElement>("a[href],button") ||
              [],
          );
          const next = trappedIndex(
            targets.indexOf(document.activeElement as HTMLElement),
            targets.length,
            event.shiftKey,
          );
          if (next < 0) return;
          event.preventDefault();
          targets[next].focus();
        }}
      >
        <nav className="nav" aria-label="More">
          {NAV.map((group) => {
            const items = group.items.filter(
              (item) => !TAB_BAR.includes(item.id),
            );
            return items.length ? (
              <div className="nav-group" key={group.group}>
                <span className="eyebrow">{group.group}</span>
                {items.map((item) => (
                  <NavLink key={item.id} item={item} {...props} />
                ))}
              </div>
            ) : null;
          })}
        </nav>
      </div>
    </>
  );
}
