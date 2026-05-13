import { Button, Card, CardContent, CardHeader, Chip, Input } from "@heroui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { listBlacklistedJobs, purgeBlacklist, unblacklistJobs } from "../../api/client";
import { ConfirmDialog } from "../../components/ConfirmDialog";

function optionalPositiveInteger(value: string): number | undefined | null {
  if (!value.trim()) {
    return undefined;
  }
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) {
    return null;
  }
  return parsed;
}

export function BlacklistPage() {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const [olderThanDays, setOlderThanDays] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [confirmPurge, setConfirmPurge] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const params = useMemo(
    () => ({
      limit: 100,
      text: text || undefined
    }),
    [text]
  );
  const blacklist = useQuery({
    queryKey: ["blacklist", params],
    queryFn: () => listBlacklistedJobs(params),
    staleTime: 15_000
  });
  const rows = blacklist.data?.items ?? [];
  const invalidate = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["blacklist"] }),
      queryClient.invalidateQueries({ queryKey: ["jobs"] }),
      queryClient.invalidateQueries({ queryKey: ["stats"] })
    ]);
  const unblacklistMutation = useMutation({
    mutationFn: (jobIds: string[]) => unblacklistJobs(jobIds),
    onError: (error: Error) => setMutationError(error.message || "Blacklist command failed"),
    onSuccess: () => {
      setMutationError(null);
      setSelectedIds(new Set());
      return invalidate();
    }
  });
  const purgeMutation = useMutation({
    mutationFn: (days?: number) => purgeBlacklist(days),
    onError: (error: Error) => setMutationError(error.message || "Blacklist command failed"),
    onSuccess: () => {
      setMutationError(null);
      setConfirmPurge(false);
      return invalidate();
    }
  });
  const purgeAge = optionalPositiveInteger(olderThanDays);

  const toggleSelected = (jobId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(jobId)) {
        next.delete(jobId);
      } else {
        next.add(jobId);
      }
      return next;
    });
  };

  return (
    <section className="mx-auto grid max-w-[1500px] gap-4" aria-label="Blacklist">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-zinc-950">Blacklist</h2>
          <p className="mt-1 text-sm text-zinc-500">
            {blacklist.data?.total ?? 0} blocked job fingerprints
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <Input
            aria-label="Search blacklist"
            onChange={(event) => setText(event.target.value)}
            placeholder="Search title, company, location"
            value={text}
            variant="secondary"
          />
          <Input
            aria-label="Blacklist age days"
            min="1"
            onChange={(event) => setOlderThanDays(event.target.value)}
            placeholder="Age days"
            type="number"
            value={olderThanDays}
            variant="secondary"
          />
          <Button
            isDisabled={selectedIds.size === 0 || unblacklistMutation.isPending}
            onPress={() => unblacklistMutation.mutate([...selectedIds])}
            variant="outline"
          >
            <RotateCcw aria-hidden="true" size={16} />
            Unblacklist selected
          </Button>
          <Button
            isDisabled={purgeMutation.isPending || purgeAge === null}
            onPress={() => setConfirmPurge(true)}
            variant="danger"
          >
            <Trash2 aria-hidden="true" size={16} />
            {olderThanDays ? "Purge aged blacklist" : "Purge all"}
          </Button>
        </div>
      </div>

      {mutationError ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
          {mutationError}
        </div>
      ) : null}
      {blacklist.isError ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
          Unable to load blacklist entries.
        </div>
      ) : null}

      <Card className="border border-zinc-200 shadow-sm" variant="default">
        <CardHeader className="flex items-center justify-between gap-3 p-4">
          <div className="flex items-center gap-2">
            <Search aria-hidden="true" className="text-zinc-500" size={16} />
            <span className="text-sm font-semibold text-zinc-700">Blocked entries</span>
          </div>
          <Chip color="default" size="sm" variant="soft">
            {selectedIds.size} selected
          </Chip>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <div className="min-w-[760px]">
              <div className="grid grid-cols-[44px_minmax(240px,2fr)_minmax(160px,1fr)_180px_180px] border-y border-zinc-200 bg-zinc-100 px-4 py-3 text-xs font-bold uppercase text-zinc-500">
                <span />
                <span>Role</span>
                <span>Company</span>
                <span>Location</span>
                <span>Blacklisted</span>
              </div>
              {blacklist.isLoading ? (
                <div className="px-4 py-5 text-sm text-zinc-500">Loading blacklist</div>
              ) : null}
              {rows.map((job) => (
                <div
                  className="grid min-h-14 grid-cols-[44px_minmax(240px,2fr)_minmax(160px,1fr)_180px_180px] items-center border-b border-zinc-100 px-4 py-2 text-sm"
                  key={job.job_id}
                >
                  <input
                    aria-label={`Select ${job.title}`}
                    checked={selectedIds.has(job.job_id)}
                    className="size-4 accent-zinc-950"
                    onChange={() => toggleSelected(job.job_id)}
                    type="checkbox"
                  />
                  <span className="font-semibold text-zinc-950">{job.title}</span>
                  <span className="truncate text-zinc-700">{job.company}</span>
                  <span className="truncate text-zinc-600">{job.location}</span>
                  <span className="text-zinc-500">{job.blacklisted_at}</span>
                </div>
              ))}
              {!blacklist.isLoading && rows.length === 0 ? (
                <div className="px-4 py-8 text-sm text-zinc-500">No blacklist entries</div>
              ) : null}
            </div>
          </div>
        </CardContent>
      </Card>
      <ConfirmDialog
        confirmLabel="Confirm purge blacklist"
        description={
          purgeAge === undefined
            ? "This removes every blacklist entry. Previously blocked jobs may be imported again if future searches find them."
            : `This removes blacklist entries older than ${purgeAge} days. It does not restore active job rows.`
        }
        isOpen={confirmPurge}
        isPending={purgeMutation.isPending}
        onCancel={() => setConfirmPurge(false)}
        onConfirm={() => purgeMutation.mutate(purgeAge ?? undefined)}
        title="Purge blacklist entries?"
      />
    </section>
  );
}
