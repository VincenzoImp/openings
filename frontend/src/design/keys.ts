// Keyboard rules shared by components, kept free of React for unit tests.

/** The tab an arrow, Home or End key moves to; null for any other key. */
export function nextTabIndex(key: string, current: number, length: number) {
  if (length < 1) return null;
  if (key === "Home") return 0;
  if (key === "End") return length - 1;
  const step = key === "ArrowRight" ? 1 : key === "ArrowLeft" ? -1 : 0;
  if (!step) return null;
  return (Math.max(current, 0) + step + length) % length;
}

/** Where Tab goes inside a container that keeps focus: it wraps at both ends. */
export function trappedIndex(
  current: number,
  length: number,
  backwards: boolean,
) {
  if (length < 1) return -1;
  if (current < 0) return backwards ? length - 1 : 0;
  return (current + (backwards ? -1 : 1) + length) % length;
}
