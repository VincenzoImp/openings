import { Button, Card, CardContent, CardHeader, Chip, Input } from "@heroui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { listBlacklistedJobs, purgeBlacklist, unblacklistJobs } from "../../api/client";
import { AlertBanner } from "../../components/AlertBanner";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { PageHeader } from "../../components/PageHeader";

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
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [olderThanDays, setOlderThanDays] = useState("");
  const [page, setPage] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [confirmPurge, setConfirmPurge] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const limit = 100;
  const params = useMemo(
    () => ({
      company: company || undefined,
      limit,
      location: location || undefined,
      offset: page * limit,
      text: text || undefined
    }),
    [company, limit, location, page, text]
  );
  const blacklist = useQuery({
    queryKey: ["blacklist", params],
    queryFn: () => listBlacklistedJobs(params),
    staleTime: 15_000
  });
  const rows = blacklist.data?.items ?? [];
  const pageCount = Math.max(1, Math.ceil((blacklist.data?.total ?? 0) / limit));
  const canGoBack = page > 0;
  const canGoForward = page + 1 < pageCount;

  useEffect(() => {
    setPage(0);
    setSelectedIds(new Set());
  }, [company, location, text]);

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
      <PageHeader
        actions={
          <>
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
          </>
        }
        description={`${blacklist.data?.total ?? 0} blocked job fingerprints`}
        title="Blacklist"
      />

      <Card className="border border-zinc-200 bg-white shadow-sm" variant="default">
        <CardContent className="grid gap-3 p-4 lg:grid-cols-[minmax(220px,1fr)_180px_180px_160px] lg:items-end">
          <label className="grid gap-1.5 text-sm font-medium text-zinc-700">
            <span>Search</span>
            <Input
              aria-label="Search blacklist"
              onChange={(event) => setText(event.target.value)}
              placeholder="Search title, company, location"
              value={text}
              variant="secondary"
            />
          </label>
          <label className="grid gap-1.5 text-sm font-medium text-zinc-700">
            <span>Company</span>
            <Input
              aria-label="Blacklist company"
              onChange={(event) => setCompany(event.target.value)}
              placeholder="Company"
              value={company}
              variant="secondary"
            />
          </label>
          <label className="grid gap-1.5 text-sm font-medium text-zinc-700">
            <span>Location</span>
            <Input
              aria-label="Blacklist location"
              onChange={(event) => setLocation(event.target.value)}
              placeholder="Location"
              value={location}
              variant="secondary"
            />
          </label>
          <label className="grid gap-1.5 text-sm font-medium text-zinc-700">
            <span>Age days</span>
            <Input
              aria-label="Blacklist age days"
              min="1"
              onChange={(event) => setOlderThanDays(event.target.value)}
              placeholder="Age days"
              type="number"
              value={olderThanDays}
              variant="secondary"
            />
          </label>
        </CardContent>
      </Card>

      {mutationError ? (
        <AlertBanner kind="danger">{mutationError}</AlertBanner>
      ) : null}
      {blacklist.isError ? (
        <AlertBanner kind="danger">Unable to load blacklist entries.</AlertBanner>
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
          <div className="hidden grid-cols-[44px_minmax(240px,2fr)_minmax(160px,1fr)_180px_180px] border-y border-zinc-200 bg-zinc-100 px-4 py-3 text-xs font-bold uppercase text-zinc-500 md:grid">
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
              className="grid min-h-20 grid-cols-[32px_minmax(0,1fr)] items-start gap-2 border-b border-zinc-100 px-4 py-3 text-sm md:min-h-14 md:grid-cols-[44px_minmax(240px,2fr)_minmax(160px,1fr)_180px_180px] md:items-center md:gap-0 md:py-2"
              key={job.job_id}
            >
              <input
                aria-label={`Select ${job.title}`}
                checked={selectedIds.has(job.job_id)}
                className="size-4 accent-zinc-950"
                onChange={() => toggleSelected(job.job_id)}
                type="checkbox"
              />
              <span className="grid gap-1 font-semibold text-zinc-950">
                {job.title}
                <small className="font-normal text-zinc-500 md:hidden">
                  {job.company} / {job.location} / {job.blacklisted_at}
                </small>
              </span>
              <span className="hidden truncate text-zinc-700 md:inline">{job.company}</span>
              <span className="hidden truncate text-zinc-600 md:inline">{job.location}</span>
              <span className="hidden text-zinc-500 md:inline">{job.blacklisted_at}</span>
            </div>
          ))}
          {!blacklist.isLoading && rows.length === 0 ? (
            <div className="px-4 py-8 text-sm text-zinc-500">No blacklist entries</div>
          ) : null}
        </CardContent>
      </Card>
      <div
        className="flex flex-wrap items-center gap-2 text-sm text-zinc-600"
        aria-label="Blacklist pagination"
      >
        <Button
          isDisabled={!canGoBack || blacklist.isLoading}
          onPress={() => setPage((value) => value - 1)}
          variant="outline"
        >
          Previous blacklist page
        </Button>
        <span className="min-w-24 text-center">
          Page {page + 1} of {pageCount}
        </span>
        <Button
          isDisabled={!canGoForward || blacklist.isLoading}
          onPress={() => setPage((value) => value + 1)}
          variant="outline"
        >
          Next blacklist page
        </Button>
      </div>
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
