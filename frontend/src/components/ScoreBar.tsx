/** A score as a number plus a small signed bar: positive fills right, negative left. */
export function ScoreBar({ score, max = 100 }: { score: number; max?: number }) {
  const magnitude = Math.min(Math.abs(score), max) / max;
  const positive = score >= 0;
  return (
    <span className="inline-flex items-center gap-2" title={`Relevance score ${score}`}>
      <span className="relative h-1.5 w-14 overflow-hidden rounded bg-surface-2">
        <span
          className={`absolute top-0 h-full ${positive ? "left-1/2 bg-positive" : "right-1/2 bg-negative"}`}
          style={{ width: `${magnitude * 50}%` }}
        />
      </span>
      <span className={`tabular w-8 text-right text-xs ${positive ? "text-fg" : "text-negative"}`}>
        {score}
      </span>
    </span>
  );
}
