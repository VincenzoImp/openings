import { useState, type FormEvent, type ReactNode } from "react";
import { CircleAlert } from "lucide-react";
import { api, call } from "../api/client";
import { Button } from "../ui/Button";
import { Field, Input } from "../ui/Field";
import { BrandMark } from "../ui/Icon";
import { Callout } from "../ui/Page";
import "./auth.css";

/** The browser session: whether an owner exists and is signed in. */
export interface Session {
  configured: boolean;
  /** A new installation asks for the one-time code printed to its log. */
  setup_code?: boolean;
  authenticated: boolean;
  csrf_token?: string;
}

/** The frame of the screens shown before the workspace: one card. */
export function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <main className="auth">
      <section className="auth-card">
        <span className="auth-brand">
          <BrandMark size={24} />
          Openings
        </span>
        {children}
      </section>
    </main>
  );
}

/** A failure before the workspace opens, with Try again when it can help. */
export function AuthError({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div role="alert">
      <Callout
        icon={CircleAlert}
        tone="danger"
        title={message}
        actions={
          retry && (
            <Button size="sm" onClick={retry}>
              Try again
            </Button>
          )
        }
      />
    </div>
  );
}

/** Sign in, or choose the owner password of a new installation. */
export function Auth({
  configured,
  setupCode = false,
  onSuccess,
}: {
  configured: boolean;
  setupCode?: boolean;
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
      const code = String(form.get("setup_code") || "").trim();
      const session = configured
        ? await call(api.POST("/api/v1/auth/login", { body: { password } }))
        : await call(
            api.POST("/api/v1/auth/setup", {
              body: { password, setup_code: code || null },
            }),
          );
      onSuccess(session as Session);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to sign in.");
    } finally {
      setPending(false);
    }
  }
  return (
    <AuthFrame>
      <h1>{configured ? "Sign in" : "Set up your workspace"}</h1>
      {!configured && (
        <p className="auth-lead">
          Choose the owner password of this installation.
        </p>
      )}
      <form className="auth-form" onSubmit={submit}>
        {error && <AuthError message={error} />}
        {!configured && setupCode && (
          <Field
            label="Setup code"
            hint="Printed in the server's log when it starts: run docker compose logs openings (or docker logs openings) and look for “Setup code”."
          >
            <Input
              name="setup_code"
              required
              autoFocus
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              placeholder="XXXX-XXXX"
              maxLength={50}
            />
          </Field>
        )}
        <Field
          label={configured ? "Password" : "Choose a password"}
          hint={configured ? undefined : "At least 10 characters."}
        >
          <Input
            name="password"
            type="password"
            minLength={configured ? 1 : 10}
            required
            autoFocus={configured || !setupCode}
            autoComplete={configured ? "current-password" : "new-password"}
          />
        </Field>
        {!configured && (
          <Field label="Confirm password">
            <Input
              name="confirm"
              type="password"
              minLength={10}
              required
              autoComplete="new-password"
            />
          </Field>
        )}
        <Button variant="primary" type="submit" disabled={pending}>
          {configured ? "Sign in" : "Create workspace"}
        </Button>
      </form>
    </AuthFrame>
  );
}
