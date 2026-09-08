import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, getToken, setToken } from "../../api/client";
import { JOB_STATUSES } from "../../api/types";
import type { ExportFormat, JobStatus } from "../../api/types";
import { useToast } from "../../app/toast";
import { Badge, STATUS_TONE } from "../../components/Badge";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/Dialog";
import { ErrorNotice, Spinner } from "../../components/EmptyState";
import { Field, Input, Select } from "../../components/Field";
import { STATUS_LABELS, formatDateTime } from "../shared/format";
import {
  keys,
  useBlacklist,
  useCleanupPreview,
  useDistribution,
  useJobCommands,
  useStats,
} from "../shared/queries";

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
      {children}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

type Pending =
  | { kind: "cleanup" }
  | { kind: "below"; score: number }
  | { kind: "stale"; days: number }
  | { kind: "purge"; days: number | null };

export function SystemView() {
  const client = useQueryClient();
  const toast = useToast();
  const stats = useStats();
  const [binSize, setBinSize] = useState(10);
  const distribution = useDistribution(binSize);
  const preview = useCleanupPreview();
  const commands = useJobCommands();
  const [blacklistText, setBlacklistText] = useState("");
  const blacklist = useBlacklist({ limit: 50, text: blacklistText.trim() || undefined });
  const [pending, setPending] = useState<Pending | null>(null);
  const [belowScore, setBelowScore] = useState("0");
  const [staleDays, setStaleDays] = useState("90");
  const [purgeDays, setPurgeDays] = useState("");
  const [exportStatuses, setExportStatuses] = useState<JobStatus[]>(["applied"]);
  const [exportFormat, setExportFormat] = useState<ExportFormat>("csv");
  const [tokenDraft, setTokenDraft] = useState(getToken() ?? "");
  const auth = useQuery({ queryKey: keys.auth, queryFn: api.dashboardAuth });

  const refreshAll = () => client.invalidateQueries();
  const fail = (error: unknown) =>
    toast.push(error instanceof Error ? error.message : String(error), "error");

  const cleanup = useMutation({
    mutationFn: api.cleanupRun,
    onSuccess: (report) => {
      toast.push(`Cleanup deleted ${report.total_deleted} rows`, "success");
      refreshAll();
    },
    onError: fail,
  });
  const below = useMutation({
    mutationFn: api.deleteBelowScore,
    onSuccess: (result) => {
      toast.push(`${result.affected_count} deleted`, "success");
      refreshAll();
    },
    onError: fail,
  });
  const stale = useMutation({
    mutationFn: api.deleteStale,
    onSuccess: (result) => {
      toast.push(`${result.affected_count} deleted`, "success");
      refreshAll();
    },
    onError: fail,
  });
  const purge = useMutation({
    mutationFn: api.purgeBlacklist,
    onSuccess: (result) => {
      toast.push(`${result.affected_count} blacklist entries purged`, "success");
      refreshAll();
    },
    onError: fail,
  });
  const exportJobs = useMutation({
    mutationFn: () => api.exportJobs({ status: exportStatuses, limit: 0 }, exportFormat),
    onError: fail,
  });

  const maxCount = Math.max(1, ...(distribution.data ?? []).map(([, count]) => count));

  const confirmPending = () => {
    if (!pending) {
      return;
    }
    if (pending.kind === "cleanup") {
      cleanup.mutate();
    } else if (pending.kind === "below") {
      below.mutate(pending.score);
    } else if (pending.kind === "stale") {
      stale.mutate(pending.days);
    } else {
      purge.mutate(pending.days);
    }
  };

  const pendingText = (): string => {
    if (!pending) {
      return "";
    }
    switch (pending.kind) {
      case "cleanup":
        return "Run the configured retention now? Only jobs still in status new are affected.";
      case "below":
        return `Delete every job in status new with a score below ${pending.score}?`;
      case "stale":
        return `Delete every job in status new not seen for ${pending.days} days?`;
      case "purge":
        return pending.days === null
          ? "Remove every blacklist entry? Those postings can be ingested again."
          : `Remove blacklist entries older than ${pending.days} days?`;
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-lg font-semibold">System</h1>
        <p className="text-sm text-slate-500">
          Database health, retention, blacklist, export and dashboard access.
        </p>
      </header>

      <Card title="Overview">
        {stats.isPending ? <Spinner /> : null}
        {stats.error ? <ErrorNotice error={stats.error} /> : null}
        {stats.data ? (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
              <Stat label="Jobs" value={stats.data.total_jobs} />
              <Stat label="New today" value={stats.data.new_today} />
              <Stat label="Seen today" value={stats.data.seen_today} />
              <Stat label="Average score" value={stats.data.avg_relevance_score} />
              <Stat label="Blacklisted" value={stats.data.blacklisted} />
            </div>
            <div className="flex flex-wrap gap-2">
              {JOB_STATUSES.map((status) => (
                <Badge key={status} tone={STATUS_TONE[status]}>
                  {STATUS_LABELS[status]} {stats.data.by_status[status] ?? 0}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
      </Card>

      <Card title="Score distribution">
        <div className="mb-2 flex items-center gap-2">
          <label htmlFor="bin-size" className="text-xs text-slate-500">
            Bin size
          </label>
          <Select
            id="bin-size"
            className="!w-20"
            value={binSize}
            onChange={(event) => setBinSize(Number(event.target.value))}
          >
            {[5, 10, 20].map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </Select>
        </div>
        {distribution.data && distribution.data.length === 0 ? (
          <p className="text-sm text-slate-500">No jobs stored.</p>
        ) : null}
        <ul className="flex flex-col gap-1">
          {distribution.data?.map(([start, count]) => (
            <li key={start} className="flex items-center gap-2 text-xs">
              <span className="w-16 text-right tabular-nums text-slate-600">
                {start} to {start + binSize - 1}
              </span>
              <span className="h-3 flex-1 rounded bg-slate-100">
                <span
                  className={`block h-full rounded ${start < 0 ? "bg-rose-400" : "bg-emerald-500"}`}
                  style={{ width: `${(count / maxCount) * 100}%` }}
                />
              </span>
              <span className="w-10 tabular-nums">{count}</span>
            </li>
          ))}
        </ul>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Retention">
          {preview.data ? (
            <p className="mb-3 text-sm text-slate-600">
              Configured cleanup would delete <strong>{preview.data.deleted_below_score}</strong>{" "}
              below the save threshold and <strong>{preview.data.deleted_stale}</strong> stale,
              purge <strong>{preview.data.purged_blacklist}</strong> blacklist entries and protect{" "}
              <strong>{preview.data.protected}</strong> jobs you acted on.
            </p>
          ) : null}
          <div className="flex flex-col gap-3">
            <Button className="w-fit" onClick={() => setPending({ kind: "cleanup" })}>
              Run configured cleanup
            </Button>
            <div className="flex items-end gap-2">
              <Field label="Delete new jobs below score" htmlFor="below-score">
                <Input
                  id="below-score"
                  type="number"
                  className="!w-28"
                  value={belowScore}
                  onChange={(event) => setBelowScore(event.target.value)}
                />
              </Field>
              <Button onClick={() => setPending({ kind: "below", score: Number(belowScore) })}>
                Delete
              </Button>
            </div>
            <div className="flex items-end gap-2">
              <Field label="Delete new jobs not seen for days" htmlFor="stale-days">
                <Input
                  id="stale-days"
                  type="number"
                  min={1}
                  className="!w-28"
                  value={staleDays}
                  onChange={(event) => setStaleDays(event.target.value)}
                />
              </Field>
              <Button
                disabled={Number(staleDays) < 1}
                onClick={() => setPending({ kind: "stale", days: Number(staleDays) })}
              >
                Delete
              </Button>
            </div>
          </div>
        </Card>

        <Card title="Export">
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2">
              {JOB_STATUSES.map((status) => (
                <label key={status} className="flex items-center gap-1 text-sm">
                  <input
                    type="checkbox"
                    checked={exportStatuses.includes(status)}
                    onChange={(event) =>
                      setExportStatuses((current) =>
                        event.target.checked
                          ? [...current, status]
                          : current.filter((value) => value !== status),
                      )
                    }
                  />
                  {STATUS_LABELS[status]}
                </label>
              ))}
            </div>
            <div className="flex items-end gap-2">
              <Field label="Format" htmlFor="export-format">
                <Select
                  id="export-format"
                  className="!w-28"
                  value={exportFormat}
                  onChange={(event) => setExportFormat(event.target.value as ExportFormat)}
                >
                  <option value="csv">CSV</option>
                  <option value="json">JSON</option>
                </Select>
              </Field>
              <Button
                variant="primary"
                disabled={exportStatuses.length === 0 || exportJobs.isPending}
                onClick={() => exportJobs.mutate()}
              >
                Download
              </Button>
            </div>
          </div>
        </Card>
      </div>

      <Card title="Blacklist">
        <div className="mb-3 flex flex-wrap items-end gap-2">
          <Field label="Search" htmlFor="blacklist-search">
            <Input
              id="blacklist-search"
              className="!w-64"
              placeholder="title, company or location"
              value={blacklistText}
              onChange={(event) => setBlacklistText(event.target.value)}
            />
          </Field>
          <Field label="Purge entries older than days (empty = all)" htmlFor="purge-days">
            <Input
              id="purge-days"
              type="number"
              min={0}
              className="!w-28"
              value={purgeDays}
              onChange={(event) => setPurgeDays(event.target.value)}
            />
          </Field>
          <Button
            variant="danger"
            onClick={() =>
              setPending({ kind: "purge", days: purgeDays === "" ? null : Number(purgeDays) })
            }
          >
            Purge
          </Button>
        </div>
        {blacklist.isPending ? <Spinner /> : null}
        {blacklist.error ? <ErrorNotice error={blacklist.error} /> : null}
        {blacklist.data ? (
          <>
            <p className="mb-2 text-xs text-slate-500">
              {blacklist.data.total} entries{blacklist.data.total > 50 ? ", showing 50" : ""}
            </p>
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-slate-500">
                <tr>
                  <th className="py-1 pr-2 font-medium">Title</th>
                  <th className="py-1 pr-2 font-medium">Company</th>
                  <th className="py-1 pr-2 font-medium">Location</th>
                  <th className="py-1 pr-2 font-medium">Since</th>
                  <th className="py-1 pr-2" />
                </tr>
              </thead>
              <tbody>
                {blacklist.data.items.map((entry) => (
                  <tr key={entry.job_id} className="border-t border-slate-100">
                    <td className="py-1 pr-2">{entry.title}</td>
                    <td className="py-1 pr-2">{entry.company}</td>
                    <td className="py-1 pr-2">{entry.location}</td>
                    <td className="py-1 pr-2 text-xs text-slate-500">
                      {formatDateTime(entry.blacklisted_at)}
                    </td>
                    <td className="py-1 text-right">
                      <Button size="sm" onClick={() => commands.unblacklist.mutate([entry.job_id])}>
                        Restore
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : null}
      </Card>

      <Card title="Dashboard access">
        <p className="mb-2 text-sm text-slate-600">
          {auth.data?.token_required
            ? "The server requires an API token; it is stored in this browser only."
            : "The server does not require a token."}
        </p>
        <div className="flex items-end gap-2">
          <Field label="API token" htmlFor="api-token">
            <Input
              id="api-token"
              type="password"
              className="!w-72"
              value={tokenDraft}
              onChange={(event) => setTokenDraft(event.target.value)}
            />
          </Field>
          <Button
            variant="primary"
            onClick={() => {
              setToken(tokenDraft);
              toast.push(tokenDraft.trim() ? "Token saved" : "Token cleared", "success");
              refreshAll();
            }}
          >
            Save
          </Button>
        </div>
      </Card>

      <ConfirmDialog
        open={pending !== null}
        title="Are you sure?"
        message={pendingText()}
        confirmLabel="Proceed"
        danger
        onConfirm={confirmPending}
        onClose={() => setPending(null)}
      />
    </div>
  );
}
