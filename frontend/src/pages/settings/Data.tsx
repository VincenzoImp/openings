import { useState, type FormEvent } from "react";
import {
  ArchiveRestore,
  Download,
  Ellipsis,
  HardDrive,
  History,
  Trash2,
} from "lucide-react";
import { download, save } from "../../api/client";
import { Button, IconButton } from "../../ui/Button";
import { ConfirmDialog, Dialog } from "../../ui/Dialog";
import { Field, Input } from "../../ui/Field";
import { formatDay, formatFull } from "../../ui/format";
import { Icon } from "../../ui/Icon";
import { Menu } from "../../ui/Menu";
import { SkeletonRows } from "../../ui/Page";
import { useToast } from "../../ui/Toast";
import { ago } from "../sources/model";
import { bytes } from "./model";
import {
  useBackups,
  useDeleteBackup,
  useIsOwner,
  useWorkspaceInfo,
  type KeptBackup,
} from "./queries";
import {
  OwnerOnly,
  SettingRow,
  SettingsGroup,
  SettingsSection,
} from "./Rows";

const today = () => new Date().toISOString().slice(0, 10);

/** Backups, restore, the copies kept by the server, storage and export. */
export function Data() {
  const info = useWorkspaceInfo();
  const owner = useIsOwner();
  const toast = useToast();
  const [restoring, setRestoring] = useState(false);
  const [busy, setBusy] = useState("");
  const storage = info.data?.storage;

  async function fetchFile(path: string, fallback: string, done: string) {
    setBusy(path);
    try {
      const file = await download(path);
      save(file.blob, file.filename || fallback);
      toast.show({ message: done, tone: "success" });
    } catch (error) {
      toast.show({
        message: error instanceof Error ? error.message : "Not downloaded.",
        tone: "error",
      });
    } finally {
      setBusy("");
    }
  }

  return (
    <SettingsSection title="Data">
      <SettingRow
        title="Backup"
        control={
          <Button
            icon={Download}
            disabled={busy === "/api/v1/backup"}
            onClick={() =>
              fetchFile(
                "/api/v1/backup",
                `openings-${today()}.sqlite`,
                "Backup downloaded",
              )
            }
          >
            Download backup
          </Button>
        }
      >
        One file with everything: jobs, applications, documents and their
        files, your profile and settings
        {storage ? `, about ${bytes(storage.database_bytes)}` : ""}. Keep it
        somewhere other than this machine.
      </SettingRow>
      {owner && (
        <SettingRow
          title="Restore"
          note={<OwnerOnly />}
          control={
            <Button icon={ArchiveRestore} onClick={() => setRestoring(true)}>
              Restore from backup…
            </Button>
          }
        >
          Replace this workspace with a backup file.
        </SettingRow>
      )}
      {owner && (
        <SettingRow
          title="Export records"
          note={<OwnerOnly />}
          control={
            <Button
              variant="ghost"
              icon={Download}
              disabled={busy === "/api/v1/export"}
              onClick={() =>
                fetchFile(
                  "/api/v1/export",
                  "openings-records.json",
                  "Records exported",
                )
              }
            >
              Export
            </Button>
          }
        >
          Your records as one JSON file, without file bytes or secrets.
        </SettingRow>
      )}
      <SettingRow
        title="Storage"
        control={
          storage && (
            <span className="set-value">
              {bytes(storage.database_bytes)} used ·{" "}
              {bytes(storage.free_bytes)} free
            </span>
          )
        }
      >
        The database with every file it holds.
      </SettingRow>
      {storage && (
        <SettingRow
          title="Posting history"
          control={
            <span className="set-value">
              {storage.retention_days
                ? `${storage.retention_days} days`
                : "Kept"}
            </span>
          }
        >
          {storage.retention_days
            ? `Finished checks are kept for ${storage.retention_days} days, and always the latest ${storage.kept_runs_per_source} of each source. Jobs, applications and documents are never removed automatically. Set by the installation.`
            : "Finished checks are kept. Jobs, applications and documents are never removed automatically."}
        </SettingRow>
      )}
      {owner && <KeptCopies onDownload={fetchFile} busy={busy} />}
      <RestoreDialog
        open={restoring}
        onClose={() => setRestoring(false)}
        limit={storage?.restore_limit_bytes}
      />
    </SettingsSection>
  );
}

/** Daily backups and the copies taken before upgrades. */
function KeptCopies({
  onDownload,
  busy,
}: {
  onDownload: (path: string, name: string, done: string) => void;
  busy: string;
}) {
  const kept = useBackups();
  const remove = useDeleteBackup();
  const toast = useToast();
  const [deleting, setDeleting] = useState<KeptBackup | null>(null);
  if (kept.isPending) return <SkeletonRows rows={3} />;
  if (kept.isError)
    return (
      <p className="set-row-desc set-danger" role="alert">
        The kept backups could not be read. {kept.error.message}
      </p>
    );
  const { items, schedule } = kept.data;
  const daily = items.filter((item) => item.kind === "scheduled");
  const copies = items.filter((item) => item.kind === "pre_upgrade");
  const path = (item: KeptBackup) =>
    `/api/v1/backups/${encodeURIComponent(item.name)}`;
  const downloadButton = (item: KeptBackup) => (
    <IconButton
      icon={Download}
      label={`Download ${item.name}`}
      size="sm"
      tooltip="above"
      disabled={busy === path(item)}
      onClick={() => onDownload(path(item), item.name, "Backup downloaded")}
    />
  );
  const failed =
    schedule.last_attempt?.outcome === "failed" || schedule.ok === false;
  return (
    <>
      <SettingsGroup title="Automatic backups" note={<OwnerOnly />}>
        <p className="set-row-desc">
          {!schedule.enabled ? (
            "Automatic backups are off for this installation."
          ) : failed ? (
            <span className="set-danger">
              The last automatic backup failed
              {schedule.last_attempt?.error
                ? `: ${schedule.last_attempt.error}`
                : "."}
            </span>
          ) : (
            <>
              Every {schedule.interval_hours ?? 24} h
              {schedule.last_at
                ? ` · the last one ${ago(schedule.last_at)}`
                : ""}{" "}
              · the latest {schedule.keep ?? 3} are kept
            </>
          )}
        </p>
        {daily.length > 0 && (
          <ul className="set-list" aria-label="Automatic backups">
            {daily.map((item) => (
              <li key={item.name} className="set-item">
                <Icon icon={History} className="set-item-icon" />
                <span className="set-item-text">
                  <span
                    className="set-item-title"
                    title={formatFull(item.created_at)}
                  >
                    {formatFull(item.created_at)}
                  </span>
                  <span className="set-item-sub">
                    {bytes(item.size_bytes)}
                  </span>
                </span>
                {downloadButton(item)}
              </li>
            ))}
          </ul>
        )}
      </SettingsGroup>
      {copies.length > 0 && (
        <SettingsGroup title="Copies before upgrades" note={<OwnerOnly />}>
          <p className="set-row-desc">
            Taken before each upgrade changed the database. Delete the ones you
            no longer need.
          </p>
          <ul className="set-list" aria-label="Copies before upgrades">
            {copies.map((item) => (
              <li key={item.name} className="set-item">
                <Icon icon={HardDrive} className="set-item-icon" />
                <span className="set-item-text">
                  <span
                    className="set-item-title"
                    title={formatFull(item.created_at)}
                  >
                    {formatDay(item.created_at)}
                  </span>
                  <span className="set-item-sub">
                    {bytes(item.size_bytes)}
                  </span>
                </span>
                {downloadButton(item)}
                <Menu
                  label={`Actions for ${item.name}`}
                  placement="bottom-end"
                  items={[
                    {
                      id: "delete",
                      label: "Delete…",
                      icon: Trash2,
                      danger: true,
                      onSelect: () => setDeleting(item),
                    },
                  ]}
                  trigger={(props) => (
                    <IconButton
                      {...props}
                      icon={Ellipsis}
                      label={`More actions for ${item.name}`}
                      size="sm"
                      tooltip="above"
                    />
                  )}
                />
              </li>
            ))}
          </ul>
        </SettingsGroup>
      )}
      <ConfirmDialog
        open={!!deleting}
        title="Delete this copy?"
        confirm="Delete copy"
        onClose={() => setDeleting(null)}
        onConfirm={() => {
          const item = deleting;
          if (!item) return;
          remove.mutate(item.name, {
            onSuccess: () =>
              toast.show({
                message: `Deleted the copy of ${formatDay(item.created_at)}`,
                tone: "success",
              }),
            onError: (error) =>
              toast.show({ message: error.message, tone: "error" }),
          });
        }}
      >
        {deleting
          ? `The copy taken on ${formatFull(deleting.created_at)} (${bytes(deleting.size_bytes)}) is deleted for good. Your workspace does not change.`
          : ""}
      </ConfirmDialog>
    </>
  );
}

/**
 * Restore: what is replaced and what is kept, then the file. The page
 * reloads once the workspace is restored.
 */
function RestoreDialog({
  open,
  onClose,
  limit,
}: {
  open: boolean;
  onClose: () => void;
  limit?: number;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const tooLarge = !!file && limit != null && file.size > limit;
  const close = () => {
    if (pending) return;
    setFile(null);
    setError("");
    onClose();
  };
  async function restore(event: FormEvent) {
    event.preventDefault();
    if (!file || tooLarge) {
      setError(file ? "" : "Choose a backup file first.");
      return;
    }
    setPending(true);
    setError("");
    try {
      await download("/api/v1/backup/restore", {
        method: "POST",
        body: file,
        headers: { "Content-Type": "application/vnd.sqlite3" },
      });
      location.reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Not restored.");
      setPending(false);
    }
  }
  return (
    <Dialog
      open={open}
      onClose={close}
      dismissible={false}
      title="Restore from backup"
      footer={
        <>
          <Button variant="ghost" onClick={close} disabled={pending}>
            Cancel
          </Button>
          <Button
            variant="danger"
            type="submit"
            form="restore-form"
            disabled={pending || !file || tooLarge}
          >
            {pending ? "Restoring…" : "Replace this workspace"}
          </Button>
        </>
      }
    >
      <form
        id="restore-form"
        className="set-form"
        noValidate
        onSubmit={restore}
      >
        <dl className="set-restore">
          <div>
            <dt>Replaced</dt>
            <dd>
              Everything in this workspace now: jobs, applications, documents
              and their files, your profile, preferences, templates, sources
              and settings.
            </dd>
          </div>
          <div>
            <dt>Kept</dt>
            <dd>
              Your password, your API tokens and this browser's sign-in.
            </dd>
          </div>
        </dl>
        <p className="set-row-desc">
          Download a backup first if you may want today's state back.
        </p>
        <Field
          label="Backup file"
          error={
            error ||
            (tooLarge
              ? `This file is ${bytes(file!.size)}; the data volume takes up to ${bytes(limit!)}.`
              : undefined)
          }
          hint={limit != null ? `Up to ${bytes(limit)}.` : undefined}
        >
          <Input
            type="file"
            className="set-file"
            accept=".sqlite,.sqlite3,.db"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setError("");
            }}
          />
        </Field>
      </form>
    </Dialog>
  );
}
