// The rows of a line-by-line comparison, kept apart from React so the folding
// can be tested without a browser.

export interface DiffLine {
  change: "same" | "added" | "removed";
  text: string;
}

export type DiffRow = DiffLine | { change: "folded"; count: number };

/** Unchanged lines kept around each change; longer unchanged runs are folded. */
const CONTEXT = 2;

/** The rows shown: every change, with a little unchanged text around it. */
export function foldDiff(lines: DiffLine[], context = CONTEXT): DiffRow[] {
  const changed = lines.map((line) => line.change !== "same");
  const rows: DiffRow[] = [];
  lines.forEach((line, index) => {
    const near = changed
      .slice(Math.max(0, index - context), index + context + 1)
      .some(Boolean);
    if (near) {
      rows.push(line);
      return;
    }
    const last = rows[rows.length - 1];
    if (last && last.change === "folded") last.count += 1;
    else rows.push({ change: "folded", count: 1 });
  });
  return rows;
}
