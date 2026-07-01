import { Card, CardContent, CardHeader, Chip } from "@heroui/react";
import { useQuery } from "@tanstack/react-query";

import { getDistribution, getFacets, getStats } from "../../api/client";
import type { FacetItem } from "../../api/types";
import { AlertBanner } from "../../components/AlertBanner";
import { Metric } from "../../components/Metric";
import { PageHeader } from "../../components/PageHeader";

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
  const facets = useQuery({
    queryKey: ["job-facets"],
    queryFn: getFacets,
    staleTime: 60_000
  });
  const maxCount = Math.max(...(distribution.data?.map(([, count]) => count) ?? []), 1);
  const hasError = stats.isError || distribution.isError || facets.isError;

  return (
    <section className="mx-auto grid max-w-[1500px] gap-4" aria-label="Analytics">
      <PageHeader
        description="Score, source, and pipeline health across the job database"
        title="Analytics"
      />

      {hasError ? <AlertBanner kind="danger">Unable to load analytics data.</AlertBanner> : null}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
        <Metric label="Total jobs" value={stats.data?.total_jobs ?? 0} />
        <Metric label="Seen today" value={stats.data?.seen_today ?? 0} />
        <Metric label="New today" value={stats.data?.new_today ?? 0} />
        <Metric label="Applied" value={stats.data?.applied ?? 0} />
        <Metric label="Blacklisted" value={stats.data?.blacklisted ?? 0} />
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

      <div className="grid gap-4 xl:grid-cols-4">
        <FacetSummary title="Sources" items={facets.data?.sites ?? []} />
        <FacetSummary title="Companies" items={facets.data?.companies ?? []} />
        <FacetSummary title="Locations" items={facets.data?.locations ?? []} />
        <FacetSummary title="Job types" items={facets.data?.job_types ?? []} />
      </div>
    </section>
  );
}

function FacetSummary({ title, items }: { title: string; items: FacetItem[] }) {
  const max = Math.max(...items.map((item) => item.count), 1);
  return (
    <Card className="border border-slate-200 shadow-sm" variant="default">
      <CardHeader className="p-4">
        <h3 className="text-base font-semibold text-slate-950">{title}</h3>
      </CardHeader>
      <CardContent className="grid gap-3 p-4 pt-0">
        {items.slice(0, 6).map((item) => (
          <div className="grid gap-1" key={String(item.value)}>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="truncate text-slate-700">{String(item.value)}</span>
              <strong className="text-slate-950">{item.count}</strong>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-zinc-900"
                style={{ width: `${Math.max(8, (item.count / max) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
