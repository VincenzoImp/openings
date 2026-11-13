import { cx } from "./classes";
import { foldDiff, type DiffLine } from "./lines";

const SPOKEN = { added: "Added: ", removed: "Removed: ", same: "" };
const MARKS = { added: "+", removed: "−", same: "" };

/** Two texts compared line by line: removed lines, then the lines that replace them. */
export function TextDiff({
  lines,
  label,
}: {
  lines: DiffLine[];
  label: string;
}) {
  return (
    <ol className="diff" aria-label={label}>
      {foldDiff(lines).map((row, index) =>
        row.change === "folded" ? (
          <li key={index} className="folded">
            {row.count === 1
              ? "1 unchanged line"
              : `${row.count} unchanged lines`}
          </li>
        ) : (
          <li key={index} className={cx(row.change !== "same" && row.change)}>
            <span className="mark" aria-hidden="true">
              {MARKS[row.change]}
            </span>
            {SPOKEN[row.change] && (
              <span className="sr">{SPOKEN[row.change]}</span>
            )}
            {row.text}
          </li>
        ),
      )}
    </ol>
  );
}
