// The address agents and upload links use (OPENINGS_PUBLIC_URL) against the
// one this browser opened. No React: tested directly (tests/shell.test.mjs).

const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);

/**
 * What to tell the owner when the dashboard is open at an address the public
 * URL does not name, such as http://nas.local:8080 while agents are sent to
 * http://127.0.0.1:8080; null when they agree or the browser runs on the server.
 */
export function addressNotice(
  publicOrigin: string | null | undefined,
  here: string,
) {
  if (!publicOrigin) return null;
  let browser: URL;
  let advertised: URL;
  try {
    browser = new URL(here);
    advertised = new URL(publicOrigin);
  } catch {
    return null;
  }
  if (browser.origin === advertised.origin) return null;
  if (LOOPBACK.has(browser.hostname)) return null;
  return {
    used: advertised.origin,
    fix: `OPENINGS_PUBLIC_URL=${browser.origin}`,
  };
}
