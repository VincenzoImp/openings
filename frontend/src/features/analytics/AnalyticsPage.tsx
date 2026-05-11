import { Card, CardContent, CardHeader, Chip } from "@heroui/react";
import { useQuery } from "@tanstack/react-query";

import { getDistribution, getStats } from "../../api/client";

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
    <section className="mx-auto grid max-w-[1500px] gap-4" aria-label="Analytics">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Metric label="Total jobs" value={stats.data?.total_jobs ?? 0} />
        <Metric label="Seen today" value={stats.data?.seen_today ?? 0} />
        <Metric label="Applied" value={stats.data?.applied ?? 0} />
        <Metric label="Average score" value={stats.data?.avg_relevance_score ?? 0} />
      </div>

      <Card className="border border-slate-200 shadow-sm" variant="default">
        <CardHeader className="flex items-center justify-between gap-3 p-4">
          <h2 className="text-lg font-semibold text-slate-950">Score distribution</h2>
          <Chip color="default" size="sm" variant="soft">
            {distribution.data?.length ?? 0} bins
          </Chip>
        </CardHeader>
        <CardContent className="grid gap-3 p-4 pt-0">
          {distribution.data?.map(([binStart, count]) => (
            <div className="grid grid-cols-[72px_minmax(0,1fr)_40px] items-center gap-3" key={binStart}>
              <span className="text-sm text-slate-600">{scoreLabel(binStart)}</span>
              <div className="h-3 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-emerald-700"
                  style={{ width: `${Math.max(8, (count / maxCount) * 100)}%` }}
                />
              </div>
              <strong className="text-right text-sm text-slate-950">{count}</strong>
            </div>
          ))}
        </CardContent>
      </Card>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <Card className="border border-slate-200 shadow-sm" variant="default">
      <CardContent className="grid min-h-24 gap-2 p-4">
        <span className="text-xs font-bold uppercase text-slate-500">{label}</span>
        <strong className="text-3xl font-semibold leading-none text-slate-950">{value}</strong>
      </CardContent>
    </Card>
  );
}
