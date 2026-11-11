import { useEffect, useState } from "react";
import { api, setCsrf, type Session } from "./api";
import { ErrorBanner, Loading } from "./design";
import { Auth, AuthFrame } from "./shell/Auth";
import { Shell } from "./shell/Shell";

/** Session bootstrap: the sign-in screen, or the workspace shell. */
export default function App() {
  const [session, setSession] = useState<Session | null>(null),
    [error, setError] = useState<string | null>(null);
  async function bootstrap() {
    try {
      setError(null);
      const result = await api<Session>("/auth/session");
      setCsrf(result.csrf_token || "");
      setSession(result);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to reach your workspace.",
      );
    }
  }
  useEffect(() => {
    void bootstrap();
    const expired = () => {
      setCsrf("");
      setSession({ configured: true, authenticated: false });
    };
    window.addEventListener("openings:unauthorized", expired);
    return () => window.removeEventListener("openings:unauthorized", expired);
  }, []);
  if (error)
    return (
      <AuthFrame>
        <h1>Unable to load the workspace</h1>
        <ErrorBanner message={error} retry={bootstrap} />
      </AuthFrame>
    );
  if (!session)
    return (
      <main className="auth">
        <Loading />
      </main>
    );
  if (!session.authenticated)
    return (
      <Auth
        configured={session.configured}
        onSuccess={(value) => {
          setCsrf(value.csrf_token || "");
          setSession(value);
        }}
      />
    );
  return (
    <Shell
      onLogout={async () => {
        await api("/auth/logout", "POST");
        await bootstrap();
      }}
    />
  );
}
