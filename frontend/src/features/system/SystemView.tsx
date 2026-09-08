import { useState, useSyncExternalStore } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";

import { TOKEN_CHANGED_EVENT, api, getToken, setToken } from "../../api/client";
import { JOB_STATUSES } from "../../api/types";
import type { ExportFormat, JobStatus } from "../../api/types";
import { useConfirm } from "../../app/confirmContext";
import { saveBlob } from "../../app/download";
import { useTheme } from "../../app/theme";
import type { ThemePreference } from "../../app/theme";
import { useToast } from "../../app/toastContext";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { ErrorNotice, Skeleton } from "../../components/EmptyState";
import { Checkbox, Field, Input, Select } from "../../components/Field";
import { Stat } from "../../components/Stat";
import { Table } from "../../components/Table";
import { formatDateTime, formatNumber } from "../shared/format";
import { STATUS_LABELS, STATUS_TONE } from "../shared/labels";
import {
  keys,
  useBlacklist,
  useCleanupPreview,
  useDistribution,
  useJobCommands,
  useSettings,
  useSettingsReference,
  useStats,
} from "../shared/queries";

const THEMES: { value: ThemePreference; label: string; hint: string }[] = [
  { value: "system", label: "System", hint: "Follows the operating system" },
  { value: "light", label: "Light", hint: "" },
  { value: "dark", label: "Dark", hint: "" },
];

function AppearanceCard() {
  const theme = useTheme();
  return (
    <Card title="Appearance">
      <fieldset>
        <legend className="sr-only">Theme</legend>
        <div className="flex flex-wrap gap-4">
          {THEMES.map((entry) => (
            <label
              key={entry.value}
              className="inline-flex cursor-pointer items-center gap-2 text-sm"
            >
              <input
                type="radio"
                name="theme"
                value={entry.value}
                checked={theme.preference === entry.value}
                onChange={() => theme.setPreference(entry.value)}
                className="accent-accent"
              />
              {entry.label}
              {entry.hint ? <span className="text-xs text-fg-faint">{entry.hint}</span> : null}
            </label>
          ))}
        </div>
      </fieldset>
    </Card>
  );
}

function OverviewCard() {
  const stats = useStats();
  return (
    <Card title="Overview">
      {stats.isPending ? <Skeleton lines={2} /> : null}
      {stats.error ? <ErrorNotice error={stats.error} onRetry={() => stats.refetch()} /> : null}
      {stats.data ? (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-7">
            <Stat label="Jobs" value={stats.data.total_jobs} />
            <Stat label="New today" value={stats.data.new_today} />
            <Stat label="Seen today" value={stats.data.seen_today} />
            <Stat label="Average score" value={stats.data.avg_relevance_score} />
            <Stat label="Blacklisted" value={stats.data.blacklisted} />
            <Stat label="Attachments" value={stats.data.attachments} />
            <Stat label="Notes" value={stats.data.notes} />
          </div>
          <div className="flex flex-wrap gap-2">
            {JOB_STATUSES.filter((status) => status !== "blacklisted").map((status) => (
              <Badge key={status} tone={STATUS_TONE[status]}>
                {STATUS_LABELS[status]} {formatNumber(stats.data.by_status[status] ?? 0)}
              </Badge>
            ))}
          </div>
        </div>
      ) : null}
    </Card>
  );
}

function DistributionCard() {
  const [binSize, setBinSize] = useState(10);
  const distribution = useDistribution(binSize);
  const maxCount = Math.max(1, ...(distribution.data ?? []).map(([, count]) => count));
  return (
    <Card
      title="Score distribution"
      actions={
        <label className="flex items-center gap-2 text-xs text-fg-muted">
          Bin
          <Select
            aria-label="Bin size"
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
        </label>
      }
    >
      {distribution.error ? <ErrorNotice error={distribution.error} /> : null}
      {distribution.data && distribution.data.length === 0 ? (
        <p className="text-sm text-fg-muted">No jobs stored.</p>
      ) : null}
      <ul className="flex flex-col gap-1">
        {distribution.data?.map(([start, count]) => (
          <li key={start} className="flex items-center gap-2 text-xs">
            <span className="tabular w-20 shrink-0 text-right text-fg-muted">
              {start} to {start + binSize - 1}
            </span>
            <span className="h-3 min-w-0 flex-1 rounded bg-surface-2">
              <span
                className={`block h-full rounded ${start < 0 ? "bg-negative/70" : "bg-positive"}`}
                style={{ width: `${(count / maxCount) * 100}%` }}
              />
            </span>
            <span className="tabular w-12 shrink-0">{formatNumber(count)}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function RetentionCard() {
  const client = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const preview = useCleanupPreview();
  const [belowScore, setBelowScore] = useState("0");
  const [staleDays, setStaleDays] = useState("90");
  const refresh = () => client.invalidateQueries();
  const fail = (error: unknown) =>
    toast.push(error instanceof Error ? error.message : String(error), "error");

  const cleanup = useMutation({
    mutationFn: api.cleanupRun,
    onSuccess: (report) => {
      toast.push(`Cleanup deleted ${report.total_deleted} jobs`, "success");
      return refresh();
    },
    onError: fail,
  });
  const below = useMutation({
    mutationFn: (score: number) => api.deleteBelowScore(score),
    onSuccess: (result) => {
      toast.push(`${result.affected_count} deleted`, "success");
      return refresh();
    },
    onError: fail,
  });
  const stale = useMutation({
    mutationFn: (days: number) => api.deleteStale(days),
    onSuccess: (result) => {
      toast.push(`${result.affected_count} deleted`, "success");
      return refresh();
    },
    onError: fail,
  });

  const runCleanup = async () => {
    const report = preview.data ?? (await api.cleanupPreview());
    const ok = await confirm({
      title: "Run the configured cleanup?",
      message: `${report.deleted_below_score} new jobs below the save threshold and ${report.deleted_stale} new jobs not seen lately are deleted. Nothing else is touched: shortlisted, applied, later statuses and blacklisted jobs (${report.protected}) stay.`,
      confirmLabel: `Delete ${report.total_deleted}`,
      danger: true,
    });
    if (ok) {
      cleanup.mutate();
    }
  };
  const runBelow = async () => {
    const score = Number(belowScore);
    try {
      const dry = await api.deleteBelowScore(score, true);
      const ok = await confirm({
        title: `Delete new jobs below score ${score}?`,
        message: `${dry.affected_count} jobs in status New match. Notes and files on them are deleted too.`,
        confirmLabel: `Delete ${dry.affected_count}`,
        danger: true,
      });
      if (ok) {
        below.mutate(score);
      }
    } catch (error) {
      fail(error);
    }
  };
  const runStale = async () => {
    const days = Number(staleDays);
    try {
      const dry = await api.deleteStale(days, true);
      const ok = await confirm({
        title: `Delete new jobs not seen for ${days} days?`,
        message: `${dry.affected_count} jobs in status New match.`,
        confirmLabel: `Delete ${dry.affected_count}`,
        danger: true,
      });
      if (ok) {
        stale.mutate(days);
      }
    } catch (error) {
      fail(error);
    }
  };

  return (
    <Card title="Retention">
      {preview.data ? (
        <p className="mb-3 text-sm text-fg-muted">
          Cleanup only ever removes jobs still in status New: right now{" "}
          <strong className="text-fg">{formatNumber(preview.data.deleted_below_score)}</strong>{" "}
          below the save threshold and{" "}
          <strong className="text-fg">{formatNumber(preview.data.deleted_stale)}</strong> not seen
          lately. Everything you acted on, blacklisted included, stays (
          <strong className="text-fg">{formatNumber(preview.data.protected)}</strong> jobs).
        </p>
      ) : null}
      <div className="flex flex-col gap-3">
        <Button className="w-fit" onClick={() => void runCleanup()} disabled={cleanup.isPending}>
          Run configured cleanup…
        </Button>
        <div className="grid grid-cols-[1fr_auto] items-end gap-2 sm:max-w-sm">
          <Field label="Delete new jobs below score" htmlFor="below-score">
            <Input
              id="below-score"
              type="number"
              inputMode="numeric"
              value={belowScore}
              onChange={(event) => setBelowScore(event.target.value)}
            />
          </Field>
          <Button onClick={() => void runBelow()} disabled={below.isPending}>
            Delete…
          </Button>
        </div>
        <div className="grid grid-cols-[1fr_auto] items-end gap-2 sm:max-w-sm">
          <Field label="Delete new jobs not seen for days" htmlFor="stale-days">
            <Input
              id="stale-days"
              type="number"
              inputMode="numeric"
              min={1}
              value={staleDays}
              onChange={(event) => setStaleDays(event.target.value)}
            />
          </Field>
          <Button
            disabled={Number(staleDays) < 1 || stale.isPending}
            onClick={() => void runStale()}
          >
            Delete…
          </Button>
        </div>
      </div>
    </Card>
  );
}

function ExportCard() {
  const toast = useToast();
  const [statuses, setStatuses] = useState<JobStatus[]>(["applied"]);
  const [format, setFormat] = useState<ExportFormat>("csv");
  const exportJobs = useMutation({
    mutationFn: () => api.exportJobs({ statuses, limit: 0 }, format),
    onSuccess: (download) => saveBlob(download.blob, download.filename),
    onError: (error) => toast.push(error instanceof Error ? error.message : String(error), "error"),
  });
  return (
    <Card title="Export">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-x-3 gap-y-2">
          {JOB_STATUSES.map((status) => (
            <Checkbox
              key={status}
              label={STATUS_LABELS[status]}
              checked={statuses.includes(status)}
              onChange={(event) =>
                setStatuses((current) =>
                  event.target.checked
                    ? [...current, status]
                    : current.filter((value) => value !== status),
                )
              }
            />
          ))}
        </div>
        <div className="grid grid-cols-[1fr_auto] items-end gap-2 sm:max-w-xs">
          <Field label="Format" htmlFor="export-format">
            <Select
              id="export-format"
              value={format}
              onChange={(event) => setFormat(event.target.value as ExportFormat)}
            >
              <option value="csv">CSV</option>
              <option value="json">JSON</option>
            </Select>
          </Field>
          <Button
            variant="primary"
            disabled={statuses.length === 0 || exportJobs.isPending}
            onClick={() => exportJobs.mutate()}
          >
            {exportJobs.isPending ? "Preparing…" : "Download"}
          </Button>
        </div>
      </div>
    </Card>
  );
}

const BLACKLIST_PAGE = 25;

function BlacklistCard() {
  const commands = useJobCommands();
  const [text, setText] = useState("");
  const [page, setPage] = useState(0);
  const blacklist = useBlacklist({
    limit: BLACKLIST_PAGE,
    offset: page * BLACKLIST_PAGE,
    text: text.trim() || undefined,
  });
  const total = blacklist.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / BLACKLIST_PAGE));
  return (
    <Card
      title="Blacklist"
      actions={
        <Input
          aria-label="Search the blacklist"
          placeholder="Search…"
          autoComplete="off"
          className="!w-40 sm:!w-56"
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            setPage(0);
          }}
        />
      }
      padded={false}
    >
      {blacklist.isPending ? (
        <div className="p-3">
          <Skeleton lines={3} />
        </div>
      ) : null}
      {blacklist.error ? (
        <div className="p-3">
          <ErrorNotice error={blacklist.error} onRetry={() => blacklist.refetch()} />
        </div>
      ) : null}
      {blacklist.data ? (
        <>
          <Table
            rows={blacklist.data.items}
            rowKey={(entry) => entry.job_id}
            minWidth={560}
            empty="Nothing blacklisted."
            columns={[
              {
                key: "title",
                header: "Title",
                render: (entry) => (
                  <div className="min-w-0">
                    <div className="truncate font-medium">{entry.title}</div>
                    <div className="truncate text-xs text-fg-muted sm:hidden">{entry.company}</div>
                  </div>
                ),
              },
              {
                key: "company",
                header: "Company",
                compact: true,
                render: (entry) => entry.company,
              },
              {
                key: "location",
                header: "Location",
                compact: true,
                render: (entry) => entry.location,
              },
              {
                key: "since",
                header: "Since",
                render: (entry) => (
                  <span className="text-xs text-fg-muted">
                    {formatDateTime(entry.status_changed_at)}
                  </span>
                ),
              },
              {
                key: "actions",
                header: "",
                align: "right",
                render: (entry) => (
                  <Button size="sm" onClick={() => commands.unblacklist.mutate([entry.job_id])}>
                    <RotateCcw size={14} aria-hidden="true" /> Restore
                  </Button>
                ),
              },
            ]}
          />
          {total > BLACKLIST_PAGE ? (
            <div className="flex items-center justify-between border-t border-edge px-3 py-2 text-xs text-fg-muted">
              <span className="tabular">
                {formatNumber(total)} entries · page {page + 1} of {pages}
              </span>
              <div className="flex gap-1">
                <Button
                  size="sm"
                  disabled={page === 0}
                  onClick={() => setPage((value) => value - 1)}
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  disabled={page + 1 >= pages}
                  onClick={() => setPage((value) => value + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </Card>
  );
}

function SettingsCard() {
  const settings = useSettings();
  const [showReference, setShowReference] = useState(false);
  const reference = useSettingsReference(showReference);
  const data = settings.data;
  return (
    <Card
      title="Settings"
      actions={
        <Button size="sm" variant="ghost" onClick={() => setShowReference((value) => !value)}>
          {showReference ? "Hide reference" : "Reference"}
        </Button>
      }
    >
      {settings.isPending ? <Skeleton lines={4} /> : null}
      {settings.error ? (
        <ErrorNotice error={settings.error} onRetry={() => settings.refetch()} />
      ) : null}
      {data ? (
        <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-[11px] uppercase tracking-wide text-fg-muted">Version</dt>
            <dd>{data.version}</dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide text-fg-muted">Profile</dt>
            <dd className="truncate">
              {data.profile.name || "unnamed"}
              {data.profile.headline ? ` · ${data.profile.headline}` : ""}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide text-fg-muted">Thresholds</dt>
            <dd className="tabular">
              save ≥ {data.scoring.save_threshold} · notify ≥ {data.scoring.notify_threshold}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide text-fg-muted">Scheduler</dt>
            <dd>
              every {data.scheduler.interval_hours} h
              {data.scheduler.run_on_startup ? ", runs on startup" : ""}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide text-fg-muted">Sources</dt>
            <dd>
              {data.sources.jobspy.enabled
                ? `${data.sources.jobspy.sites.join(", ")}: ${data.sources.jobspy.queries.length} queries × ${data.sources.jobspy.locations.length} locations`
                : "boards disabled"}
              {data.sources.companies.length
                ? ` · ${data.sources.companies.length} company feeds`
                : ""}
              {data.sources.feeds.length ? ` · ${data.sources.feeds.length} RSS feeds` : ""}
              {data.sources.adzuna.enabled ? " · Adzuna" : ""}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide text-fg-muted">Embeddings</dt>
            <dd>{data.embeddings.enabled ? data.embeddings.status : "disabled"}</dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide text-fg-muted">Notifications</dt>
            <dd>{data.notifications.telegram ? "Telegram" : "none"}</dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide text-fg-muted">Retention</dt>
            <dd>
              {data.retention.max_age_days} days · attachments up to {data.attachments.max_size_mb}{" "}
              MB
            </dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide text-fg-muted">Time zone</dt>
            <dd>{data.timezone}</dd>
          </div>
          <div className="min-w-0">
            <dt className="text-[11px] uppercase tracking-wide text-fg-muted">Data directory</dt>
            <dd className="truncate font-mono text-xs" title={data.data_dir}>
              {data.data_dir}
            </dd>
          </div>
        </dl>
      ) : null}
      {showReference ? (
        <pre
          tabIndex={0}
          className="mt-3 max-h-96 overflow-auto rounded bg-surface-2 p-3 text-[11px] text-fg"
        >
          {reference.isPending
            ? "Loading…"
            : reference.error
              ? String(reference.error)
              : reference.data}
        </pre>
      ) : null}
    </Card>
  );
}

function subscribeToken(callback: () => void): () => void {
  window.addEventListener(TOKEN_CHANGED_EVENT, callback);
  return () => window.removeEventListener(TOKEN_CHANGED_EVENT, callback);
}

function AccessCard() {
  const client = useQueryClient();
  const toast = useToast();
  const [draft, setDraft] = useState("");
  const auth = useQuery({ queryKey: keys.auth, queryFn: api.dashboardAuth });
  const stored = useSyncExternalStore(subscribeToken, () => Boolean(getToken()));
  const apply = (value: string | null) => {
    setToken(value);
    setDraft("");
    toast.push(value ? "Token saved" : "Token cleared", "success");
    void client.invalidateQueries();
  };
  return (
    <Card title="Dashboard access">
      <p className="mb-2 text-sm text-fg-muted">
        {auth.data?.token_required
          ? `The server requires an API token. ${stored ? "One is stored in this browser." : "None is stored in this browser."}`
          : "The server does not require a token."}
      </p>
      <form
        className="grid grid-cols-[1fr_auto_auto] items-end gap-2 sm:max-w-lg"
        onSubmit={(event) => {
          event.preventDefault();
          if (draft.trim()) {
            apply(draft);
          }
        }}
      >
        <Field label="API token" htmlFor="api-token">
          <Input
            id="api-token"
            type="password"
            autoComplete="off"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
        </Field>
        <Button type="submit" variant="primary" disabled={!draft.trim()}>
          Save
        </Button>
        <Button disabled={!stored} onClick={() => apply(null)}>
          Clear
        </Button>
      </form>
    </Card>
  );
}

export function SystemView() {
  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-lg font-semibold">System</h1>
        <p className="text-sm text-fg-muted">
          Appearance, database health, retention, blacklist, export, settings and access.
        </p>
      </header>
      <AppearanceCard />
      <OverviewCard />
      <DistributionCard />
      <div className="grid gap-4 lg:grid-cols-2">
        <RetentionCard />
        <ExportCard />
      </div>
      <BlacklistCard />
      <SettingsCard />
      <AccessCard />
    </div>
  );
}
