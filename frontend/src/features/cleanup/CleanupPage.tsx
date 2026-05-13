import { Button, Card, CardContent, CardHeader, Input } from "@heroui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DatabaseZap, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  deleteJobsBelowScore,
  deleteStaleJobs,
  previewCleanup,
  purgeCleanupBlacklist,
  runCleanup
} from "../../api/client";

export function CleanupPage() {
  const queryClient = useQueryClient();
  const [confirmed, setConfirmed] = useState(false);
  const [score, setScore] = useState("25");
  const [days, setDays] = useState("30");
  const [blacklistDays, setBlacklistDays] = useState("90");
  const cleanup = useQuery({
    queryKey: ["cleanup-preview"],
    queryFn: previewCleanup,
    staleTime: 15_000
  });
  const invalidate = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] }),
      queryClient.invalidateQueries({ queryKey: ["jobs"] }),
      queryClient.invalidateQueries({ queryKey: ["stats"] }),
      queryClient.invalidateQueries({ queryKey: ["distribution"] }),
      queryClient.invalidateQueries({ queryKey: ["blacklist"] })
    ]);
  const runCleanupMutation = useMutation({
    mutationFn: runCleanup,
    onSuccess: () => {
      setConfirmed(false);
      return invalidate();
    }
  });
  const belowScoreMutation = useMutation({
    mutationFn: deleteJobsBelowScore,
    onSuccess: invalidate
  });
  const staleMutation = useMutation({
    mutationFn: deleteStaleJobs,
    onSuccess: invalidate
  });
  const blacklistMutation = useMutation({
    mutationFn: purgeCleanupBlacklist,
    onSuccess: invalidate
  });
  const preview = cleanup.data;

  return (
    <section className="mx-auto grid max-w-[1500px] gap-4" aria-label="Cleanup">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-zinc-950">Cleanup</h2>
          <p className="mt-1 text-sm text-zinc-500">Controlled database maintenance</p>
        </div>
        <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2">
          <label className="flex h-9 items-center gap-2 text-sm font-semibold text-red-900">
            <input
              aria-label="Confirm cleanup"
              checked={confirmed}
              className="size-4 accent-red-700"
              onChange={(event) => setConfirmed(event.target.checked)}
              type="checkbox"
            />
            Confirm cleanup
          </label>
          <Button
            isDisabled={!confirmed || runCleanupMutation.isPending}
            onPress={() => {
              if (confirmed) {
                runCleanupMutation.mutate();
              }
            }}
            variant="danger"
          >
            <DatabaseZap aria-hidden="true" size={16} />
            Run configured cleanup
          </Button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <Metric label="Total preview" value={preview?.total_deleted ?? 0} />
        <Metric label="Below score" value={preview?.deleted_below_score ?? 0} />
        <Metric label="Stale" value={preview?.deleted_stale ?? 0} />
        <Metric label="Blacklist purge" value={preview?.purged_blacklist ?? 0} />
        <Metric
          label="Protected"
          value={(preview?.protected_applied ?? 0) + (preview?.protected_bookmarked ?? 0)}
        />
      </div>

      <Card className="border border-zinc-200 shadow-sm" variant="default">
        <CardHeader className="flex items-center gap-2 p-4">
          <ShieldCheck aria-hidden="true" className="text-zinc-500" size={18} />
          <h3 className="text-base font-semibold text-zinc-950">Manual cleanup commands</h3>
        </CardHeader>
        <CardContent className="grid gap-3 p-4 pt-0 lg:grid-cols-3">
          <div className="grid gap-2 rounded-md border border-zinc-200 p-3">
            <Input
              aria-label="Score threshold"
              min="0"
              onChange={(event) => setScore(event.target.value)}
              type="number"
              value={score}
              variant="secondary"
            />
            <Button
              isDisabled={belowScoreMutation.isPending}
              onPress={() => belowScoreMutation.mutate(Number(score))}
              variant="danger"
            >
              <Trash2 aria-hidden="true" size={16} />
              Delete below score
            </Button>
          </div>
          <div className="grid gap-2 rounded-md border border-zinc-200 p-3">
            <Input
              aria-label="Stale days"
              min="1"
              onChange={(event) => setDays(event.target.value)}
              type="number"
              value={days}
              variant="secondary"
            />
            <Button
              isDisabled={staleMutation.isPending}
              onPress={() => staleMutation.mutate(Number(days))}
              variant="danger"
            >
              <Trash2 aria-hidden="true" size={16} />
              Delete stale jobs
            </Button>
          </div>
          <div className="grid gap-2 rounded-md border border-zinc-200 p-3">
            <Input
              aria-label="Blacklist age days"
              min="1"
              onChange={(event) => setBlacklistDays(event.target.value)}
              type="number"
              value={blacklistDays}
              variant="secondary"
            />
            <Button
              isDisabled={blacklistMutation.isPending}
              onPress={() => blacklistMutation.mutate(Number(blacklistDays))}
              variant="danger"
            >
              <Trash2 aria-hidden="true" size={16} />
              Purge aged blacklist
            </Button>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <Card className="border border-zinc-200 bg-white shadow-sm" variant="default">
      <CardContent className="grid min-h-24 gap-2 p-4">
        <span className="text-xs font-bold uppercase text-zinc-500">{label}</span>
        <strong className="text-3xl font-semibold leading-none text-zinc-950">{value}</strong>
      </CardContent>
    </Card>
  );
}
