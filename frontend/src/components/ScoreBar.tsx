/** A score as a number plus a small signed bar; negative scores fill left in red. */
export function ScoreBar({ score, max = 100 }: { score: number; max?: number }) {
  const magnitude = Math.min(Math.abs(score), max) / max;
  const positive = score >= 0;
  return (
    <span className="inline-flex items-center gap-2" title={`Relevance score ${score}`}>
      <span className="relative h-1.5 w-16 overflow-hidden rounded bg-slate-200">
        <span
          className={`absolute top-0 h-full ${positive ? "left-1/2 bg-emerald-500" : "right-1/2 bg-rose-500"}`}
          style={{ width: `${magnitude * 50}%` }}
        />
      </span>
      <span
        className={`w-8 text-right text-xs tabular-nums ${positive ? "text-slate-800" : "text-rose-700"}`}
      >
        {score}
      </span>
    </span>
  );
}
