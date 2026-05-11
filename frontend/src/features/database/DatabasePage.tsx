import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { previewCleanup, runCleanup } from "../../api/client";
import { Button } from "../../components/ui/button";

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
      return queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] });
    }
  });

  const preview = cleanup.data;

  return (
    <section className="workspace" aria-label="Database">
      <section className="panel" aria-label="Cleanup preview">
        <div className="panel-header">
          <h2>Cleanup preview</h2>
          <strong className="panel-total">{preview?.total_deleted ?? 0}</strong>
        </div>

        <div className="metric-grid metric-grid--compact">
          <article className="metric">
            <span>Below score</span>
            <strong>{preview?.deleted_below_score ?? 0}</strong>
          </article>
          <article className="metric">
            <span>Stale</span>
            <strong>{preview?.deleted_stale ?? 0}</strong>
          </article>
          <article className="metric">
            <span>Blacklist purge</span>
            <strong>{preview?.purged_blacklist ?? 0}</strong>
          </article>
          <article className="metric">
            <span>Protected</span>
            <strong>
              {(preview?.protected_applied ?? 0) + (preview?.protected_bookmarked ?? 0)}
            </strong>
          </article>
        </div>

        <div className="danger-strip">
          <label className="toggle-field">
            <input
              aria-label="Confirm cleanup"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
              type="checkbox"
            />
            Confirm cleanup
          </label>
          <Button
            disabled={!confirmed || runCleanupMutation.isPending}
            onClick={() => {
              if (confirmed) {
                runCleanupMutation.mutate();
              }
            }}
            variant="danger"
          >
            Run cleanup
          </Button>
        </div>
      </section>
    </section>
  );
}
