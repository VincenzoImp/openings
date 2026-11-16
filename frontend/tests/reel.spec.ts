import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { test as base, expect } from "./fixtures";
import { OVERLAY, Reel, settled, SIZE } from "./reel";
import { startServer, type Server } from "./server";

// The README's demo reel (`npm run reel [-- --dark]`, scripts/reel.mjs): about
// 20 s of the real dashboard on the demo workspace (`dashboard_server.py
// --demo`), recorded with `page.screencast` as JPEG frames at 1280×800. The
// cursor, the clicks, the key chips and the captions are overlays drawn in the
// page with the dashboard's own tokens and Inter; everything under them is the
// product. The browser's clock is frozen at the moment the workspace was
// seeded, so "2h ago" and the greeting read the same in every frame, and the
// reel keeps its own clock (Reel.beat), so two runs share one timeline and
// differ only in encoder noise.
//
// The spec writes to $OPENINGS_REEL_DIR: frames/*.jpg, frames.json (each
// frame's time in seconds) and track.json (each scene with its caption and
// focal regions, the cursor path, the clicks and the keys, in seconds and page
// pixels), which the video reuses for its zooms and crops. It is its own
// Playwright project, never run in CI.
const ROOT = resolve(import.meta.dirname, "../..");
const OUT = process.env.OPENINGS_REEL_DIR;
const THEME = process.env.OPENINGS_REEL_THEME === "dark" ? "dark" : "light";
const SLUG = "github.com/VincenzoImp/openings-job-search";

/** Seed the demo workspace into a new snapshot; its owner session cookie. */
function seedDemo() {
  const directory = mkdtempSync(join(tmpdir(), "openings-reel-"));
  const snapshot = join(directory, "snapshot.sqlite");
  const seeded = spawnSync(
    "uv",
    [
      "run",
      "--project",
      ROOT,
      "python",
      join(ROOT, "backend/tests/dashboard_server.py"),
      "--seed",
      snapshot,
      "--demo",
    ],
    { encoding: "utf8", timeout: 120_000 },
  );
  const line = seeded.stdout?.match(/^\{.*\}$/m)?.[0];
  if (!line)
    throw Error(`The demo workspace was not seeded.\n${seeded.stderr}`);
  return { directory, snapshot, session: JSON.parse(line).session as string };
}

const test = base.extend<
  { session: string },
  { demo: { server: Server; session: string; directory: string } }
>({
  demo: [
    async ({}, use) => {
      const seeded = seedDemo();
      const server = await startServer({ snapshot: seeded.snapshot });
      await use({ ...seeded, server });
      await server.stop();
      rmSync(seeded.directory, { recursive: true, force: true });
    },
    { scope: "worker", timeout: 200_000 },
  ],
  baseURL: async ({ demo }, use) => use(demo.server.url),
  session: async ({ demo }, use) => use(demo.session),
  // One run, one workspace: nothing to restore.
  seededWorkspace: [async ({}, use) => use(), { auto: true }],
});

test.use({
  signedIn: false,
  viewport: SIZE,
  locale: "en-GB",
  timezoneId: "Europe/Amsterdam",
  colorScheme: THEME,
  // The overlay is a style element the served policy would refuse.
  bypassCSP: true,
});

test("demo reel", async ({ page, session }) => {
  test.skip(!OUT, "Run through `npm run reel`, which sets OPENINGS_REEL_DIR.");
  test.setTimeout(240_000);
  const [name, ...value] = session.split("=");
  await page.context().addCookies([
    {
      name,
      value: value.join("="),
      domain: "127.0.0.1",
      path: "/",
      httpOnly: true,
      sameSite: "Strict",
    },
  ]);
  // Frozen at the moment the workspace was seeded: "Found 2h ago" and the
  // greeting read the same in every frame. Timers still run.
  await page.clock.setFixedTime(new Date());
  // The theme, and the demo banner put away for the session as its close
  // button does: the reel shows the screens, not the notice above them.
  await page.addInitScript((value) => {
    try {
      localStorage.setItem("openings-theme", value);
      sessionStorage.setItem("openings-demo-banner", "dismissed");
    } catch {}
  }, THEME);
  await page.addInitScript(OVERLAY);
  // The employer's site opens in a new tab the reel does not show; nothing
  // leaves the machine.
  await page
    .context()
    .route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) =>
      route.fulfill({ contentType: "text/html", body: "" }),
    );

  const main = page.locator("#content");
  const nav = (label: string) =>
    page.locator(".ui-app-side").getByRole("link", { name: label });

  await page.goto("/#sources");
  await settled(page);
  await expect(page.getByText("Backend roles, Amsterdam")).toBeVisible();
  const reel = new Reel(page, OUT!, { theme: THEME });
  await reel.record();

  // 1. It collects: the sources, each on its own schedule, then Jobs › New.
  await reel.scene("It collects.", main);
  await reel.move(page.getByText("Backend roles, Amsterdam"));
  await reel.pause(300);
  await reel.move(page.getByText("Voltline Grid Analytics careers"));
  await reel.pause(300);
  await reel.click(nav("Jobs"));
  await settled(page);
  await expect(page.locator(".jobs-list")).toBeVisible();
  await reel.focus(page.locator(".jobs-list"));
  await reel.pause(600);

  // 2. Into Jobs › New: read each one beside the list, decide with one key.
  await reel.scene("Fresh jobs, no duplicates.", main);
  await reel.move(page.locator(".jobs-list"), { x: 220, y: 90 });
  await reel.press("j", "j");
  await reel.pause(600);
  await reel.press("s", "s");
  await reel.pause(700);
  await reel.press("d", "d");
  await reel.pause(600);
  await reel.press("z", "z");
  await reel.pause(700);

  // 3. Your agent prepares: its dismissals with a reason, its applications.
  await reel.scene("Your agent prepares.", main);
  await reel.click(page.getByRole("tab", { name: /^Dismissed/ }));
  await settled(page);
  await reel.click(
    page.locator(".jobs-list").getByRole("button", { name: /Pixelwright/ }),
  );
  await expect(page.locator(".jobs-dismissal")).toContainText("Claude Code");
  await settled(page);
  await reel.focus(page.locator(".jobs-dismissal"));
  await reel.pause(1300);

  // 4. Ranked by priority and deadline, ready to send.
  await reel.scene("Ranked, ready to send.", main);
  await reel.click(nav("Applications"));
  await settled(page);
  await reel.click(page.getByRole("tab", { name: /^Ready/ }));
  await settled(page);
  const grid = main.getByText("Senior Backend Engineer, Grid Data");
  await reel.focus(main.getByRole("tabpanel"));
  await reel.pause(500);
  await reel.click(grid);
  await settled(page);
  await expect(
    page.getByRole("button", { name: /Mark applied/ }),
  ).toBeVisible();
  await reel.focus(main.getByRole("heading", { level: 1 }));
  await reel.pause(700);
  await reel.click(main.getByRole("tab", { name: "CV" }));
  await settled(page);
  await reel.pause(1000);

  // 5. You apply: on the employer's site, then mark it applied.
  await reel.scene("You apply, best first.", main);
  const employer = main.getByRole("link", { name: /Apply on the employer/ });
  await reel.focus(employer);
  const popup = page.context().waitForEvent("page");
  await reel.click(employer);
  await (await popup).close();
  await page.bringToFront();
  // Back in front, the viewer draws the PDFs again.
  await settled(page);
  await reel.pause(400);
  await reel.focus(page.getByRole("button", { name: /Mark applied/ }));
  await reel.press("Shift+Enter", "⇧ ↵");
  await expect(main.getByText("Platform Engineer").first()).toBeVisible();
  await settled(page);
  await reel.pause(900);

  // 6. Replies, tracked: Today, then the end card.
  await reel.scene("Replies, tracked.", main);
  await reel.click(nav("Today"));
  await settled(page);
  await reel.focus(main.locator("h1").first());
  await reel.pause(1200);
  await reel.endCard(
    "Openings",
    "Every new job, filtered, prepared and ranked. You just apply.",
    "docker run --rm -p 127.0.0.1:8080:8080 vincenzoimp/openings demo",
    SLUG,
  );
  await reel.pause(2200);
  await reel.stop();
});
