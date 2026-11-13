// The synthetic servers of the browser tests (backend/tests/dashboard_server.py).
//
// The global setup (the default export) seeds one workspace into a snapshot
// file and signs the owner in once. Each Playwright worker then starts its own
// server on a private copy of that snapshot (the `server` fixture in
// fixtures.ts), and every test begins by restoring that copy to the snapshot,
// so tests never see each other's changes and run in any order and in parallel.
import { spawn, type ChildProcess } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const ROOT = resolve(import.meta.dirname, "../..");
const SCRIPT = join(ROOT, "backend/tests/dashboard_server.py");

export type Server = { url: string; stop: () => Promise<void> };

function dashboardServer(args: string[], env: NodeJS.ProcessEnv = {}) {
  return spawn("uv", ["run", "--project", ROOT, "python", SCRIPT, ...args], {
    env: { ...process.env, ...env },
    // Its own process group, so stopping it also stops Python under `uv run`.
    detached: true,
    stdio: ["ignore", "pipe", "pipe"],
  });
}

/** Resolve with the first stdout line that matches `pattern`, or reject on exit or timeout. */
function firstLine(child: ChildProcess, pattern: RegExp, timeout: number) {
  return new Promise<RegExpMatchArray>((resolve, reject) => {
    let out = "";
    let err = "";
    const exited = (code: number | null) =>
      fail(`The synthetic server exited with code ${code} before it started.`);
    const fail = (reason: string) => {
      clearTimeout(timer);
      stop(child);
      reject(Error(`${reason}\n${err.slice(-4000)}`));
    };
    const timer = setTimeout(
      () => fail(`The synthetic server did not start in ${timeout} ms.`),
      timeout,
    );
    // Keep the end of stderr for the error message; drain it either way.
    child.stderr!.on("data", (chunk) => (err = (err + chunk).slice(-8000)));
    child.stdout!.on("data", (chunk) => {
      out += chunk;
      const match = out.match(pattern);
      if (!match) return;
      clearTimeout(timer);
      child.removeListener("exit", exited);
      child.stdout!.removeAllListeners("data");
      child.stdout!.resume();
      resolve(match);
    });
    child.once("exit", exited);
  });
}

function stop(child: ChildProcess) {
  if (child.exitCode !== null || child.pid === undefined) return;
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch {}
}

/**
 * Start a synthetic server on a free port: on a copy of `snapshot`, or on a
 * workspace it seeds itself (sized by OPENINGS_E2E_JOBS/APPLICATIONS in `env`).
 */
export async function startServer({
  snapshot,
  env,
  timeout = 60_000,
}: { snapshot?: string; env?: NodeJS.ProcessEnv; timeout?: number } = {}) {
  const child = dashboardServer(
    ["--port", "0", ...(snapshot ? ["--snapshot", snapshot] : [])],
    env,
  );
  const [, url] = await firstLine(
    child,
    /Synthetic workspace at (http:\/\/127\.0\.0\.1:\d+)/,
    timeout,
  );
  // Ready once the application answers, not only once the port is open.
  const ready = Date.now() + timeout;
  while (
    !(await fetch(url + "/health").then(
      (r) => r.ok,
      () => false,
    ))
  ) {
    if (Date.now() > ready) {
      stop(child);
      throw Error(`The synthetic server at ${url} never answered /health.`);
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return {
    url,
    stop: () =>
      new Promise<void>((done) => {
        if (child.exitCode !== null) return done();
        child.once("exit", () => done());
        stop(child);
      }),
  } satisfies Server;
}

/** Global setup: seed the snapshot every worker copies and sign the owner in. */
export default async function seedWorkspace() {
  const directory = await mkdtemp(join(tmpdir(), "openings-e2e-"));
  const snapshot = join(directory, "snapshot.sqlite");
  const [line] = await firstLine(
    dashboardServer(["--seed", snapshot]),
    /^\{.*\}$/m,
    120_000,
  );
  // The cookie is signed with the snapshot's own secret: it is valid in every
  // worker's copy, so specs need not sign in (sign-in attempts are limited).
  process.env.OPENINGS_E2E_SNAPSHOT = snapshot;
  process.env.OPENINGS_E2E_SESSION = JSON.parse(line).session;
  return () => rm(directory, { recursive: true, force: true });
}
