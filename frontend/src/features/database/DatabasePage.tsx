import { Button, Card, CardContent, CardHeader } from "@heroui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { previewCleanup, runCleanup } from "../../api/client";

export function DatabasePage() {
  const queryClient = useQueryClient();
  const [confirmed, setConfirmed] = useState(false);
  const cleanup = useQuery({
    queryKey: ["cleanup-preview"],
    queryFn: previewCleanup,
    staleTime: 15_000
  });
  const runCleanupMutation = useMutation({
    mutationFn: runCleanup,
    onSuccess: () => {
      setConfirmed(false);
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] }),
        queryClient.invalidateQueries({ queryKey: ["jobs"] }),
        queryClient.invalidateQueries({ queryKey: ["stats"] }),
        queryClient.invalidateQueries({ queryKey: ["distribution"] })
      ]);
    }
  });

  const preview = cleanup.data;

  return (
    <section className="mx-auto grid max-w-[1500px] gap-4" aria-label="Database">
      <Card className="border border-slate-200 shadow-sm" variant="default">
        <CardHeader className="flex items-center justify-between gap-3 p-4">
          <h2 className="text-lg font-semibold text-slate-950">Cleanup preview</h2>
          <strong className="text-3xl font-semibold leading-none text-slate-950">
            {preview?.total_deleted ?? 0}
          </strong>
        </CardHeader>

        <CardContent className="grid gap-4 p-4 pt-0">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Metric label="Below score" value={preview?.deleted_below_score ?? 0} />
            <Metric label="Stale" value={preview?.deleted_stale ?? 0} />
            <Metric label="Blacklist purge" value={preview?.purged_blacklist ?? 0} />
            <Metric
              label="Protected"
              value={(preview?.protected_applied ?? 0) + (preview?.protected_bookmarked ?? 0)}
            />
          </div>

          <div className="flex flex-wrap items-center justify-end gap-3 rounded-lg border border-red-200 bg-red-50 p-3">
            <label className="flex h-10 items-center gap-2 text-sm font-semibold text-red-900">
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
              Run cleanup
            </Button>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <Card className="border border-slate-200 bg-white" variant="default">
      <CardContent className="grid min-h-24 gap-2 p-4">
        <span className="text-xs font-bold uppercase text-slate-500">{label}</span>
        <strong className="text-3xl font-semibold leading-none text-slate-950">{value}</strong>
      </CardContent>
    </Card>
  );
}
