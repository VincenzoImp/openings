import { useState } from "react";
import { api } from "../../api";
import { EmptyState, ErrorBanner, Icon, Loading } from "../../design";
import { buttonClass } from "../../design/classes";
import { ConfirmDialog } from "../../library/common";
import { dayTime } from "../../library/time";
import { useFresh } from "../../library/useFresh";
import { useWorkspace } from "../../state";
import { megabytes, type KeptBackup, type KeptBackups } from "./model";
import { OwnerOnly } from "./OwnerOnly";

const NONE: KeptBackups = {
  items: [],
  total: 0,
  schedule: {
    enabled: true,
    keep: 0,
    interval_hours: 24,
    last_at: null,
    age_hours: null,
    ok: false,
    last_attempt: null,
  },
};

function DownloadLink({ item }: { item: KeptBackup }) {
  return (
    <a
      className={buttonClass("quiet", "sm")}
      href={`/api/v1/backups/${encodeURIComponent(item.name)}`}
      download={item.name}
      aria-label={`Download ${item.name}`}
    >
      <Icon name="download" />
      Download
    </a>
  );
}

function Rows({
  items,
  label,
  onDelete,
}: {
  items: KeptBackup[];
  label: string;
  onDelete?: (item: KeptBackup) => void;
}) {
  return (
    <div className="datatable-wrap">
      <table className="datatable stack" aria-label={label}>
        <thead>
          <tr>
            <th>File</th>
            <th>Created</th>
            <th>Size</th>
            <th>
              <span className="sr">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.name}>
              <td className="primary">
                <span className="title">{item.name}</span>
              </td>
              <td className="meta" data-label="Created">
                {dayTime(item.created_at)}
              </td>
              <td className="meta" data-label="Size">
                {megabytes(item.size_bytes)}
              </td>
              <td className="actions">
                <div className="row" style={{ justifyContent: "flex-end" }}>
                  <DownloadLink item={item} />
                  {onDelete && (
                    <button
                      type="button"
                      className={buttonClass("quiet danger", "sm")}
                      aria-label={`Delete ${item.name}`}
                      onClick={() => onDelete(item)}
                    >
                      Delete…
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Copies the server keeps by itself: daily backups and copies taken before an upgrade. */
export function AutomaticBackups() {
  const kept = useFresh<KeptBackups>("/backups", NONE, ["backups"]);
  const { mutate } = useWorkspace();
  const [deleting, setDeleting] = useState<KeptBackup | null>(null);
  const { schedule } = kept.data;
  const daily = kept.data.items.filter((item) => item.kind === "scheduled");
  const copies = kept.data.items.filter((item) => item.kind === "pre_upgrade");
  const attempt = schedule.last_attempt;
  return (
    <section className="card" aria-labelledby="automatic-title">
      <header>
        <h2 id="automatic-title" className="grow">
          Automatic backups
        </h2>
        <OwnerOnly />
      </header>
      {kept.error ? (
        <div className="body">
          <ErrorBanner message={kept.error} retry={kept.reload} />
        </div>
      ) : kept.loading ? (
        <Loading label="Loading backups…" />
      ) : (
        <div className="body stack">
          <p>
            {schedule.enabled
              ? `Once a day the server keeps a copy of the workspace on its data volume; the ${schedule.keep} most recent are kept. `
              : "Daily backups are off (OPENINGS_BACKUP_KEEP=0). "}
            {schedule.last_at
              ? `Last backup: ${dayTime(schedule.last_at)}.`
              : schedule.enabled
                ? "The first one is written shortly after the server starts."
                : ""}
          </p>
          {attempt && attempt.outcome !== "ok" && attempt.error && (
            <ErrorBanner
              message={`The last automatic backup did not complete: ${attempt.error}`}
            />
          )}
          <p className="caption">
            These copies stay on the same machine. Download one now and then, or
            copy the backup folder elsewhere, to keep the workspace safe from a
            disk failure.
          </p>
          {daily.length ? (
            <Rows items={daily} label="Daily backups" />
          ) : (
            <EmptyState title="No daily backup yet">
              {schedule.enabled
                ? "The server writes one within a minute of starting, then once a day."
                : "Set OPENINGS_BACKUP_KEEP to a number above 0 to turn them on."}
            </EmptyState>
          )}
          {copies.length > 0 && (
            <>
              <h3>Copies before an upgrade</h3>
              <p className="caption">
                The workspace as it was before a new release changed its format.
                The two most recent are kept; delete one when you no longer need
                to go back.
              </p>
              <Rows
                items={copies}
                label="Copies before an upgrade"
                onDelete={setDeleting}
              />
            </>
          )}
        </div>
      )}
      {deleting && (
        <ConfirmDialog
          title={`Delete ${deleting.name}?`}
          confirm="Delete copy"
          keep="Keep copy"
          onClose={() => setDeleting(null)}
          onConfirm={async () => {
            if (
              await mutate(
                () =>
                  api(
                    `/backups/${encodeURIComponent(deleting.name)}`,
                    "DELETE",
                  ),
                `${deleting.name} was deleted.`,
              )
            )
              setDeleting(null);
          }}
        >
          <p>
            This removes {deleting.name} ({megabytes(deleting.size_bytes)}) from
            the data volume for good. Without it you cannot go back to the
            workspace as it was before that upgrade.
          </p>
        </ConfirmDialog>
      )}
    </section>
  );
}
