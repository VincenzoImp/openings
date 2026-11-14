import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { api as legacy, setCsrf as setLegacyCsrf, type Session } from "./api";
import { api, call, setCsrf } from "./api/client";
import { queryClient } from "./query/query";
import { ErrorBanner, Loading } from "./design";
import { Shell } from "./shell/Shell";

// Signing in is needed once per session: its code loads only then.
const Auth = lazy(() =>
  import("./shell/Auth").then((module) => ({ default: module.Auth })),
);
const AuthFrame = lazy(() =>
  import("./shell/Auth").then((module) => ({ default: module.AuthFrame })),
);

/** Both clients send the session's CSRF token until the old one is gone. */
function shareToken(token: string) {
  setCsrf(token);
  setLegacyCsrf(token);
}

/** Session bootstrap: the sign-in screen, or the workspace shell. */
export default function App() {
  const [session, setSession] = useState<Session | null>(null),
    [error, setError] = useState<string | null>(null);
  const bootstrap = useCallback(async () => {
    try {
      setError(null);
      const result = await legacy<Session>("/auth/session");
      shareToken(result.csrf_token || "");
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
      shareToken("");
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
  const waiting = (
    <main className="auth">
      <Loading />
    </main>
  );
  if (error)
    return (
      <Suspense fallback={waiting}>
        <AuthFrame>
          <h1>Unable to load the workspace</h1>
          <ErrorBanner message={error} retry={bootstrap} />
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
            shareToken(value.csrf_token || "");
            setSession(value);
          }}
        />
      </Suspense>
    );
  return <Shell onSignOut={signOut} />;
}
