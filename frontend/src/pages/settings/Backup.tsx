import { useState, type CSSProperties } from "react";
import { binary } from "../../api";
import { Banner, Button, Field, Stat, Stats } from "../../design";
import { useWorkspace } from "../../state";
import { TWO_UP, megabytes, type Storage } from "./model";
import { OwnerOnly } from "./OwnerOnly";

function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob),
    link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Back up the whole workspace, export its records, or restore a backup. */
export function Backup({ storage }: { storage?: Storage }) {
  const { mutate, pending } = useWorkspace();
  const [file, setFile] = useState<File | null>(null),
    [confirmation, setConfirmation] = useState("");
  const limit = storage?.restore_limit_bytes;
  const tooLarge = !!file && limit !== undefined && file.size > limit;
  return (
    <div className="stack">
      {storage && (
        <Stats>
          <Stat
            label="Database size"
            value={megabytes(storage.database_bytes)}
          />
          <Stat
            label="Free space on the data volume"
            value={megabytes(storage.free_bytes)}
          />
          <Stat
            label="Largest backup you can restore"
            value={megabytes(storage.restore_limit_bytes)}
            note={
              storage.restore_limit_configured_bytes === null
                ? undefined
                : "OPENINGS_MAX_RESTORE_MB applies"
            }
          />
        </Stats>
      )}
      <div className="split" style={{ "--split": TWO_UP } as CSSProperties}>
        <section className="card" aria-labelledby="backup-title">
          <header>
            <h2 id="backup-title">Back up</h2>
          </header>
          <div className="body stack">
            <p>
              One SQLite file holds everything: jobs, applications, documents
              with their files, your record and the settings. Keep it somewhere
              other than this machine.
            </p>
            <div className="row">
              <Button
                variant="primary"
                icon="download"
                disabled={pending}
                onClick={() =>
                  mutate(async () => {
                    const response = await binary("/backup", "GET");
                    save(
                      await response.blob(),
                      `openings-${new Date().toISOString().slice(0, 10)}.sqlite`,
                    );
                  }, "Backup downloaded.")
                }
              >
                Download a backup
              </Button>
              {storage && (
                <span className="caption">
                  About {megabytes(storage.database_bytes)}
                </span>
              )}
            </div>
            <p>
              The records export is a JSON file of the workspace's records
              without file bytes, with secrets in source settings removed.
            </p>
            <div className="row">
              <Button
                icon="download"
                disabled={pending}
                onClick={() =>
                  mutate(async () => {
                    const response = await binary("/export", "GET");
                    save(await response.blob(), "openings-records.json");
                  }, "Records exported.")
                }
              >
                Export records
              </Button>
            </div>
          </div>
        </section>
        <section className="card" aria-labelledby="restore-title">
          <header>
            <h2 id="restore-title" className="grow">
              Restore
            </h2>
            <OwnerOnly />
          </header>
          <form
            className="body stack"
            onSubmit={async (event) => {
              event.preventDefault();
              if (!file) return;
              const ok = await mutate(
                () =>
                  binary("/backup/restore", "POST", file, {
                    "Content-Type": "application/vnd.sqlite3",
                  }),
                "Workspace restored.",
              );
              if (ok) location.reload();
            }}
          >
            <p>
              Restoring replaces the whole workspace with the file you choose.
              Your password and the API tokens of this installation are kept.
              Download a backup first to keep the current state.
            </p>
            <Field
              label="Backup file"
              hint={
                limit === undefined
                  ? undefined
                  : tooLarge
                    ? `This file is ${megabytes(file!.size)}; with the free space on the data volume, up to ${megabytes(limit)} can be restored.`
                    : `Up to ${megabytes(limit)} with the free space on the data volume.`
              }
            >
              <input
                type="file"
                accept=".sqlite,.sqlite3,.db"
                aria-invalid={tooLarge || undefined}
                onChange={(event) => setFile(event.target.files?.[0] || null)}
              />
            </Field>
            <Field label="Type RESTORE to confirm">
              <input
                value={confirmation}
                autoComplete="off"
                onChange={(event) => setConfirmation(event.target.value)}
              />
            </Field>
            {tooLarge && (
              <Banner tone="danger">
                This file is larger than the data volume can take.
              </Banner>
            )}
            <div className="row">
              <Button
                variant="danger"
                disabled={
                  pending || !file || tooLarge || confirmation !== "RESTORE"
                }
              >
                Restore this file
              </Button>
              <span className="caption">
                {!file
                  ? "Choose a file first."
                  : confirmation !== "RESTORE"
                    ? "Type RESTORE to confirm."
                    : "The page reloads when the restore is done."}
              </span>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}
