import { Button, Card, CardContent, CardHeader, Input } from "@heroui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DatabaseZap, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  deleteJobsBelowScore,
  deleteStaleJobs,
  previewCleanup,
  purgeCleanupBlacklist,
  runCleanup,
} from "../../api/client";
import { AlertBanner } from "../../components/AlertBanner";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Metric } from "../../components/Metric";

type PendingCleanup =
  | { action: "configured"; value: null }
  | { action: "below-score"; value: number }
  | { action: "stale"; value: number }
  | { action: "blacklist"; value: number };

function positiveInteger(value: string, min = 1): number | null {
  if (!value.trim()) {
    return null;
  }
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < min) {
    return null;
  }
  return parsed;
}

export function CleanupPage() {
  const queryClient = useQueryClient();
  const [confirmed, setConfirmed] = useState(false);
  const [score, setScore] = useState("25");
  const [days, setDays] = useState("30");
  const [blacklistDays, setBlacklistDays] = useState("90");
  const [pendingCleanup, setPendingCleanup] = useState<PendingCleanup | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [mutationMessage, setMutationMessage] = useState<string | null>(null);
  const cleanup = useQuery({
    queryKey: ["cleanup-preview"],
    queryFn: previewCleanup,
    staleTime: 15_000,
  });
  const invalidate = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] }),
      queryClient.invalidateQueries({ queryKey: ["jobs"] }),
      queryClient.invalidateQueries({ queryKey: ["stats"] }),
      queryClient.invalidateQueries({ queryKey: ["distribution"] }),
      queryClient.invalidateQueries({ queryKey: ["blacklist"] }),
    ]);
  const runCleanupMutation = useMutation({
    mutationFn: runCleanup,
    onError: (error: Error) => {
      setMutationMessage(null);
      setMutationError(error.message || "Cleanup failed");
    },
    onSuccess: () => {
      setMutationError(null);
      setMutationMessage("Configured cleanup completed.");
      setConfirmed(false);
      setPendingCleanup(null);
      return invalidate();
    },
  });
  const belowScoreMutation = useMutation({
    mutationFn: deleteJobsBelowScore,
    onError: (error: Error) => {
      setMutationMessage(null);
      setMutationError(error.message || "Cleanup failed");
    },
    onSuccess: () => {
      setMutationError(null);
      setMutationMessage("Jobs below the score threshold were deleted.");
      setPendingCleanup(null);
      return invalidate();
    },
  });
  const staleMutation = useMutation({
    mutationFn: deleteStaleJobs,
    onError: (error: Error) => {
      setMutationMessage(null);
      setMutationError(error.message || "Cleanup failed");
    },
    onSuccess: () => {
      setMutationError(null);
      setMutationMessage("Stale jobs were deleted.");
      setPendingCleanup(null);
      return invalidate();
    },
  });
  const blacklistMutation = useMutation({
    mutationFn: purgeCleanupBlacklist,
    onError: (error: Error) => {
      setMutationMessage(null);
      setMutationError(error.message || "Cleanup failed");
    },
    onSuccess: () => {
      setMutationError(null);
      setMutationMessage("Aged blacklist entries were purged.");
      setPendingCleanup(null);
      return invalidate();
    },
  });
  const preview = cleanup.data;
  const scoreValue = positiveInteger(score, 0);
  const daysValue = positiveInteger(days);
  const blacklistDaysValue = positiveInteger(blacklistDays);
  const cleanupPending =
    runCleanupMutation.isPending ||
    belowScoreMutation.isPending ||
    staleMutation.isPending ||
    blacklistMutation.isPending;
  const pendingTitle =
    pendingCleanup?.action === "configured"
      ? "Run configured cleanup?"
      : pendingCleanup?.action === "below-score"
        ? "Delete jobs below score?"
        : pendingCleanup?.action === "stale"
          ? "Delete stale jobs?"
          : "Purge aged blacklist entries?";
  const pendingDescription =
    pendingCleanup?.action === "configured"
      ? "This runs the configured cleanup sequence using settings.yaml retention and scoring rules. Saved and applied jobs remain protected."
      : pendingCleanup?.action === "below-score"
        ? `This permanently deletes active jobs with relevance score below ${pendingCleanup.value}. Saved and applied jobs remain protected by the cleanup rules.`
        : pendingCleanup?.action === "stale"
          ? `This permanently deletes active jobs that have not been seen for at least ${pendingCleanup.value} days.`
          : `This removes blacklist entries older than ${pendingCleanup?.value ?? 0} days. It does not restore active jobs.`;
  const pendingConfirmLabel =
    pendingCleanup?.action === "configured"
      ? "Confirm configured cleanup"
      : pendingCleanup?.action === "below-score"
        ? "Confirm delete below score"
        : pendingCleanup?.action === "stale"
          ? "Confirm delete stale jobs"
          : "Confirm purge blacklist";
  const confirmPendingCleanup = () => {
    if (!pendingCleanup) {
      return;
    }
    if (pendingCleanup.action === "configured") {
      runCleanupMutation.mutate();
    } else if (pendingCleanup.action === "below-score") {
      belowScoreMutation.mutate(pendingCleanup.value);
    } else if (pendingCleanup.action === "stale") {
      staleMutation.mutate(pendingCleanup.value);
    } else {
      blacklistMutation.mutate(pendingCleanup.value);
    }
  };

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
                setPendingCleanup({ action: "configured", value: null });
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

      {mutationError ? <AlertBanner kind="danger">{mutationError}</AlertBanner> : null}
      {mutationMessage ? <AlertBanner kind="success">{mutationMessage}</AlertBanner> : null}
      {cleanup.isError ? (
        <AlertBanner kind="danger">Unable to load cleanup preview.</AlertBanner>
      ) : null}

      <Card className="border border-zinc-200 shadow-sm" variant="default">
        <CardHeader className="flex items-center gap-2 p-4">
          <ShieldCheck aria-hidden="true" className="text-zinc-500" size={18} />
          <h3 className="text-base font-semibold text-zinc-950">Manual cleanup commands</h3>
        </CardHeader>
        <CardContent className="grid gap-3 p-4 pt-0 lg:grid-cols-3">
          <div className="grid gap-2 rounded-md border border-zinc-200 p-3">
            <label className="grid gap-1.5 text-sm font-medium text-zinc-700">
              <span>Score threshold</span>
              <Input
                aria-label="Score threshold"
                min="0"
                onChange={(event) => setScore(event.target.value)}
                type="number"
                value={score}
                variant="secondary"
              />
            </label>
            <Button
              isDisabled={scoreValue === null || cleanupPending}
              onPress={() => {
                if (scoreValue !== null) {
                  setPendingCleanup({ action: "below-score", value: scoreValue });
                }
              }}
              variant="danger"
            >
              <Trash2 aria-hidden="true" size={16} />
              Delete below score
            </Button>
          </div>
          <div className="grid gap-2 rounded-md border border-zinc-200 p-3">
            <label className="grid gap-1.5 text-sm font-medium text-zinc-700">
              <span>Stale days</span>
              <Input
                aria-label="Stale days"
                min="1"
                onChange={(event) => setDays(event.target.value)}
                type="number"
                value={days}
                variant="secondary"
              />
            </label>
            <Button
              isDisabled={daysValue === null || cleanupPending}
              onPress={() => {
                if (daysValue !== null) {
                  setPendingCleanup({ action: "stale", value: daysValue });
                }
              }}
              variant="danger"
            >
              <Trash2 aria-hidden="true" size={16} />
              Delete stale jobs
            </Button>
          </div>
          <div className="grid gap-2 rounded-md border border-zinc-200 p-3">
            <label className="grid gap-1.5 text-sm font-medium text-zinc-700">
              <span>Blacklist age</span>
              <Input
                aria-label="Blacklist age days"
                min="1"
                onChange={(event) => setBlacklistDays(event.target.value)}
                type="number"
                value={blacklistDays}
                variant="secondary"
              />
            </label>
            <Button
              isDisabled={blacklistDaysValue === null || cleanupPending}
              onPress={() => {
                if (blacklistDaysValue !== null) {
                  setPendingCleanup({ action: "blacklist", value: blacklistDaysValue });
                }
              }}
              variant="danger"
            >
              <Trash2 aria-hidden="true" size={16} />
              Purge aged blacklist
            </Button>
          </div>
        </CardContent>
      </Card>
      <ConfirmDialog
        confirmLabel={pendingConfirmLabel}
        description={pendingDescription}
        isOpen={pendingCleanup !== null}
        isPending={cleanupPending}
        onCancel={() => setPendingCleanup(null)}
        onConfirm={confirmPendingCleanup}
        title={pendingTitle}
      />
    </section>
  );
}
