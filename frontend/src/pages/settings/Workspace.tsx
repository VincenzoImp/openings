import type { CSSProperties } from "react";
import { api } from "../../api";
import { Button, Field, Tag } from "../../design";
import { useWorkspace } from "../../state";
import { TWO_UP, megabytes, type WorkspaceInfo } from "./model";
import { OwnerOnly } from "./OwnerOnly";

/** The owner password; browser sessions sign in again, API tokens keep working. */
function Password() {
  const { mutate, pending, notify } = useWorkspace();
  return (
    <section className="card" aria-labelledby="password-title">
      <header>
        <h2 id="password-title" className="grow">
          Change the password
        </h2>
        <OwnerOnly />
      </header>
      <form
        className="body stack"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          if (form.get("password") !== form.get("confirm")) {
            notify("The passwords do not match.", true);
            return;
          }
          if (
            await mutate(
              () =>
                api("/auth/password", "POST", {
                  password: form.get("password"),
                }),
              "Password changed. Sign in with your new password.",
            )
          )
            window.dispatchEvent(new Event("openings:unauthorized"));
        }}
      >
        <p>
          API tokens keep working; every browser session must sign in again.
        </p>
        <div className="form-grid">
          <Field label="New password" hint="At least 10 characters.">
            <input
              name="password"
              type="password"
              minLength={10}
              required
              autoComplete="new-password"
            />
          </Field>
          <Field label="Confirm the new password">
            <input
              name="confirm"
              type="password"
              minLength={10}
              required
              autoComplete="new-password"
            />
          </Field>
        </div>
        <div className="row">
          <Button variant="primary" size="sm" disabled={pending}>
            Change the password
          </Button>
        </div>
      </form>
    </section>
  );
}

/** What this workspace is, how long it keeps collection history, and access. */
export function Workspace({
  info,
  onLogout,
}: {
  info: WorkspaceInfo;
  onLogout: () => void;
}) {
  const storage = info.storage;
  return (
    <div className="stack">
      <div className="split" style={{ "--split": TWO_UP } as CSSProperties}>
        <section className="card" aria-labelledby="about-title">
          <header>
            <h2 id="about-title">This workspace</h2>
          </header>
          <div className="body">
            <dl className="dl">
              <dt>Version</dt>
              <dd>{info.version || "Unknown"}</dd>
              <dt>Database schema</dt>
              <dd>{info.schema_version ?? "Unknown"}</dd>
              <dt>Public address</dt>
              <dd className="mono">{info.origin || location.origin}</dd>
              {storage && (
                <>
                  <dt>Data</dt>
                  <dd>
                    {megabytes(storage.database_bytes)} ·{" "}
                    {megabytes(storage.free_bytes)} free on the data volume
                  </dd>
                </>
              )}
              <dt>Owner</dt>
              <dd>One owner, signed in with a password</dd>
              <dt>Language</dt>
              <dd>
                English interface; your content can use any language{" "}
                <Tag>English</Tag>
              </dd>
            </dl>
          </div>
          <footer>
            <span className="caption grow">
              Theme and density are in the top bar and remembered by this
              browser.
            </span>
            <Button size="sm" icon="logout" onClick={onLogout}>
              Sign out
            </Button>
          </footer>
        </section>
        <section className="card" aria-labelledby="retention-title">
          <header>
            <h2 id="retention-title">Retention</h2>
          </header>
          <div className="body stack">
            <p>
              {storage?.retention_days
                ? `Finished collection runs and tasks are removed after ${storage.retention_days} days, except the latest ${storage.kept_runs_per_source} of each source.`
                : "Finished collection runs and tasks are kept."}
            </p>
            <p className="muted">
              Jobs, applications, documents, notes and agent run reports are
              never removed automatically.
            </p>
            <p className="caption">
              Set by the installation with OPENINGS_RETENTION_DAYS (0 keeps
              everything); a clean-up runs at start and every six hours.
            </p>
          </div>
        </section>
      </div>
      <Password />
      <p className="caption">
        <a href="/api/v1/capabilities" target="_blank" rel="noreferrer">
          Service capabilities and interface coverage
        </a>
      </p>
    </div>
  );
}
