import { useThresholds } from "../features/shared/queries";

/**
 * A relevance score: the number first, then a bar scaled to `max` (the
 * largest score in the current list, so differences stay visible). The
 * number takes the accent tone at or above the notify threshold and fades
 * below the save threshold.
 */
export function ScoreBar({ score, max = 100 }: { score: number; max?: number }) {
  const thresholds = useThresholds();
  const scale = Math.max(1, max, Math.abs(score));
  const width = Math.min(100, (Math.abs(score) / scale) * 100);
  const positive = score >= 0;
  const tone =
    score < 0 || score < thresholds.save
      ? "text-fg-faint"
      : score >= thresholds.notify
        ? "font-semibold text-accent"
        : "text-fg";
  return (
    <span className="inline-flex items-center gap-2" title={`Relevance score ${score}`}>
      <span className={`tabular w-8 text-right text-xs ${tone}`}>{score}</span>
      <span className="relative h-2 w-16 overflow-hidden rounded bg-surface-2">
        <span
          className={`absolute left-0 top-0 h-full rounded ${
            positive ? (score >= thresholds.notify ? "bg-accent" : "bg-positive/70") : "bg-negative"
          }`}
          style={{ width: `${width}%` }}
        />
      </span>
    </span>
  );
}
