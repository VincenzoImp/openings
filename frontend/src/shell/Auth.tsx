import { useState, type FormEvent, type ReactNode } from "react";
import { api, type Session } from "../api";
import { Button, ErrorBanner } from "../design";

/** The frame of the screens shown before the workspace: one card. */
export function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <main className="auth">
      <section className="auth-card card">
        <span className="brand">Openings</span>
        {children}
      </section>
    </main>
  );
}

/** Sign in, or choose the owner password of a new installation. */
export function Auth({
  configured,
  onSuccess,
}: {
  configured: boolean;
  onSuccess: (session: Session) => void;
}) {
  const [error, setError] = useState<string | null>(null),
    [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const form = new FormData(event.currentTarget),
      password = String(form.get("password") || "");
    if (!configured && password !== form.get("confirm")) {
      setError("The passwords do not match.");
      return;
    }
    setPending(true);
    try {
      onSuccess(
        await api<Session>(configured ? "/auth/login" : "/auth/setup", "POST", {
          password,
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to sign in.");
    } finally {
      setPending(false);
    }
  }
  return (
    <AuthFrame>
      <p className="eyebrow">Your job search workspace</p>
      <h1>{configured ? "Sign in to Openings" : "Set up your workspace"}</h1>
      <p className="muted">
        {configured
          ? "Enter your owner password to access your workspace."
          : "Create the owner password for this installation. Your profile, jobs and documents stay together in one workspace."}
      </p>
      <form className="stack" onSubmit={submit}>
        {error && <ErrorBanner message={error} />}
        <label className="field">
          <span>{configured ? "Password" : "Choose a password"}</span>
          <input
            name="password"
            type="password"
            minLength={configured ? 1 : 10}
            required
            autoFocus
            autoComplete={configured ? "current-password" : "new-password"}
          />
          {!configured && (
            <small className="hint">At least 10 characters.</small>
          )}
        </label>
        {!configured && (
          <label className="field">
            <span>Confirm password</span>
            <input
              name="confirm"
              type="password"
              minLength={10}
              required
              autoComplete="new-password"
            />
          </label>
        )}
        <Button variant="primary" loading={pending}>
          {configured ? "Sign in" : "Create workspace"}
        </Button>
      </form>
      <p className="caption auth-note">
        Jobs, career evidence and application documents.
      </p>
    </AuthFrame>
  );
}
