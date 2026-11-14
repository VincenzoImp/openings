import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { api, call, setCsrf } from "./api/client";
import { queryClient } from "./query/query";
import { href, navigate } from "./shell/router";
import { Shell } from "./shell/Shell";
import type { Session } from "./shell/Auth";

// Signing in is needed once per session: its code loads only then.
const Auth = lazy(() =>
  import("./shell/Auth").then((module) => ({ default: module.Auth })),
);
const AuthFrame = lazy(() =>
  import("./shell/Auth").then((module) => ({ default: module.AuthFrame })),
);
const AuthError = lazy(() =>
  import("./shell/Auth").then((module) => ({ default: module.AuthError })),
);

/** Session bootstrap: the sign-in screen, or the workspace shell. */
export default function App() {
  const [session, setSession] = useState<Session | null>(null),
    [error, setError] = useState<string | null>(null);
  const bootstrap = useCallback(async () => {
    try {
      setError(null);
      const result = (await call(api.GET("/api/v1/auth/session"))) as Session;
      setCsrf(result.csrf_token || "");
      setSession(result);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to reach your workspace.",
      );
    }
  }, []);
  useEffect(() => {
    void bootstrap();
    const expired = () => {
      setCsrf("");
      queryClient.clear();
      setSession({ configured: true, authenticated: false });
    };
    window.addEventListener("openings:unauthorized", expired);
    return () => window.removeEventListener("openings:unauthorized", expired);
  }, [bootstrap]);
  const signOut = useCallback(() => {
    void call(api.POST("/api/v1/auth/logout"))
      .catch(() => undefined)
      .then(() => {
        queryClient.clear();
        return bootstrap();
      });
  }, [bootstrap]);
  // The page stays blank for the moment the session takes to read.
  const waiting = <main className="auth" aria-busy="true" />;
  if (error)
    return (
      <Suspense fallback={waiting}>
        <AuthFrame>
          <h1>Unable to load the workspace</h1>
          <AuthError message={error} retry={bootstrap} />
        </AuthFrame>
      </Suspense>
    );
  if (!session) return waiting;
  if (!session.authenticated)
    return (
      <Suspense fallback={waiting}>
        <Auth
          configured={session.configured}
          onSuccess={(value) => {
            // A new installation starts with the first-run guide.
            if (!session.configured) navigate(href("setup"), { replace: true });
            setCsrf(value.csrf_token || "");
            setSession(value);
          }}
        />
      </Suspense>
    );
  return <Shell onSignOut={signOut} />;
}
