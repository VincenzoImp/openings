import type { CSSProperties } from "react";
import { cx } from "./classes";

/** A rate as a person reads it: 0.4286 -> "43%". */
export const percent = (rate: number) => `${Math.round(rate * 100)}%`;

/**
 * A rate or a share as a bar with its number written beside it; the bar only
 * supports the number. `count` is how many the rate counts ("43% · 6").
 */
export function RateBar({
  rate,
  count,
  tone,
}: {
  rate: number;
  count?: number;
  tone?: "attention" | "danger";
}) {
  const text = percent(rate) + (count === undefined ? "" : ` · ${count}`);
  return (
    <div className="rate">
      <div
        className={cx("meter", tone)}
        aria-hidden="true"
        style={
          {
            "--value": percent(Math.min(1, Math.max(0, rate))),
          } as CSSProperties
        }
      >
        <span />
      </div>
      <span className="num">{text}</span>
    </div>
  );
}
