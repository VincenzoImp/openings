// Multi-select and swipe, free of React so they can be tested.

/** `x` or ⌘-click: add the row, or take it out. */
export function toggleSelected(selected: ReadonlySet<string>, id: string) {
  const next = new Set(selected);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

/**
 * Shift-click: every row from the anchor (the last row toggled) to this one,
 * in list order, joins the selection. Without an anchor, the row alone.
 */
export function selectRange(
  selected: ReadonlySet<string>,
  ids: readonly string[],
  anchor: string | null,
  id: string,
) {
  const next = new Set(selected);
  const from = anchor ? ids.indexOf(anchor) : -1;
  const to = ids.indexOf(id);
  if (to < 0) return next;
  if (from < 0) return next.add(id);
  const [start, end] = from < to ? [from, to] : [to, from];
  for (const row of ids.slice(start, end + 1)) next.add(row);
  return next;
}

/** How far a row must travel, as a share of its width, to count as a swipe. */
export const SWIPE_SHARE = 0.3;
/** …and at least this many pixels. */
export const SWIPE_MIN = 72;
/** A press held this long, without moving, opens the row's menu. */
export const LONG_PRESS_MS = 500;
/** Movement that cancels a long press, in pixels. */
export const PRESS_SLOP = 8;

/**
 * Where a finished horizontal drag sends the row: "right" (shortlist),
 * "left" (dismiss) or nowhere. A drag that is mostly vertical is a scroll.
 */
export function swipeOutcome(dx: number, dy: number, width: number) {
  if (Math.abs(dx) < Math.abs(dy) * 2) return null;
  if (Math.abs(dx) < Math.max(SWIPE_MIN, width * SWIPE_SHARE)) return null;
  return dx > 0 ? ("right" as const) : ("left" as const);
}
