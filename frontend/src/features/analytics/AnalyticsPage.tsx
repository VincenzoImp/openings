import { useQuery } from "@tanstack/react-query";

import { getDistribution, getStats } from "../../api/client";
import { Badge } from "../../components/ui/badge";

function scoreLabel(binStart: number) {
  return `${binStart}-${binStart + 4}`;
}

export function AnalyticsPage() {
  const stats = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
    staleTime: 30_000
  });
  const distribution = useQuery({
    queryKey: ["distribution"],
    queryFn: getDistribution,
    staleTime: 30_000
  });
  const maxCount = Math.max(...(distribution.data?.map(([, count]) => count) ?? [1]));

  return (
    <section className="workspace" aria-label="Analytics">
      <div className="metric-grid">
        <article className="metric">
          <span>Total jobs</span>
          <strong>{stats.data?.total_jobs ?? 0}</strong>
        </article>
        <article className="metric">
          <span>Seen today</span>
          <strong>{stats.data?.seen_today ?? 0}</strong>
        </article>
        <article className="metric">
          <span>Applied</span>
          <strong>{stats.data?.applied ?? 0}</strong>
        </article>
        <article className="metric">
          <span>Average score</span>
          <strong>{stats.data?.avg_relevance_score ?? 0}</strong>
        </article>
      </div>

      <section className="panel" aria-label="Score distribution">
        <div className="panel-header">
          <h2>Score distribution</h2>
          <Badge>{distribution.data?.length ?? 0} bins</Badge>
        </div>
        <div className="bars">
          {distribution.data?.map(([binStart, count]) => (
            <div className="bar-row" key={binStart}>
              <span>{scoreLabel(binStart)}</span>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{ width: `${Math.max(8, (count / maxCount) * 100)}%` }}
                />
              </div>
              <strong>{count}</strong>
            </div>
          ))}
        </div>
      </section>
    </section>
  );
}
