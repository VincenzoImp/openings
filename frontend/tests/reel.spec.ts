import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { test as base, expect, type Locator, type Page } from "./fixtures";
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
const SIZE = { width: 1280, height: 800 };
const SLUG = "github.com/VincenzoImp/openings-job-search";

type Rect = { x: number; y: number; width: number; height: number };
type Track = {
  size: typeof SIZE;
  theme: string;
  scenes: {
    caption: string;
    start: number;
    end?: number;
    focus: { t: number; rect: Rect }[];
  }[];
  cursor: { t: number; x: number; y: number }[];
  clicks: { t: number; x: number; y: number }[];
  keys: { t: number; key: string; label: string }[];
};

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

// The overlay layer, installed in every document: a cursor that follows the
// mouse, a ring on each press, key chips at the top right, the caption at the
// bottom left and the end card. It never takes a pointer event.
const OVERLAY = `
(() => {
  const css = \`
    #reel { position: fixed; inset: 0; z-index: 2147483647; pointer-events: none;
      font-family: var(--font); -webkit-font-smoothing: antialiased; }
    #reel .cursor { position: absolute; left: 0; top: 0; width: 22px; height: 22px;
      transform: translate(-100px, -100px); }
    #reel .ring { position: absolute; width: 36px; height: 36px; margin: -18px 0 0 -18px;
      border-radius: 50%; border: 2px solid var(--accent); opacity: 0;
      animation: reel-ring 420ms ease-out; }
    @keyframes reel-ring { from { transform: scale(0.4); opacity: 0.9 }
      to { transform: scale(1.3); opacity: 0 } }
    #reel .keys { position: absolute; top: 20px; right: 24px; display: flex; gap: 8px; }
    #reel .key { min-width: 48px; height: 48px; padding: 0 14px; box-sizing: border-box;
      display: grid; place-items: center; border-radius: 8px; background: var(--surface);
      color: var(--text); border: 1px solid var(--border-strong); box-shadow: var(--shadow-md);
      font: var(--w-semibold) 24px/1 var(--font); transition: opacity 240ms; }
    #reel .caption { position: absolute; right: 24px; bottom: 24px; padding: 12px 18px;
      border-radius: 12px; background: var(--primary); color: var(--on-primary);
      font: var(--w-semibold) 26px/32px var(--font); letter-spacing: var(--tr-2xl);
      box-shadow: var(--shadow-lg); transition: opacity 200ms; }
    #reel .caption:empty { opacity: 0; }
    #reel .card { position: absolute; inset: 0; display: grid; place-content: center;
      gap: 16px; text-align: center; background: color-mix(in srgb, var(--bg) 92%, transparent);
      color: var(--text); opacity: 0; }
    #reel .card.on { opacity: 1; }
    #reel .card h2 { margin: 0; font: var(--w-semibold) 40px/48px var(--font);
      letter-spacing: var(--tr-3xl); }
    #reel .card code { justify-self: center; padding: 12px 18px; border-radius: 8px;
      background: var(--primary); color: var(--on-primary); font: 20px/28px var(--mono); }
    #reel .card p { margin: 0; font: var(--w-medium) 20px/28px var(--font); color: var(--text-2); }
    #reel .card p + code { margin-top: 16px; }
  \`;
  const cursor = \`<svg class="cursor" viewBox="0 0 22 22" aria-hidden="true">
    <path d="M3 2 L3 18 L7.5 13.8 L10.6 20.4 L13.4 19.1 L10.4 12.6 L16.6 12.6 Z"
      fill="#111113" stroke="#ffffff" stroke-width="1.5" stroke-linejoin="round"/></svg>\`;
  const mount = () => {
    if (document.getElementById("reel") || !document.body) return;
    const root = document.createElement("div");
    root.id = "reel";
    root.innerHTML = \`<style>\${css}</style>\${cursor}<div class="keys"></div>
      <div class="caption"></div><div class="card"></div>\`;
    document.body.append(root);
    const state = (window.__reel ??= { x: -100, y: -100, caption: "" });
    const place = () =>
      (root.querySelector(".cursor").style.transform =
        \`translate(\${state.x - 3}px, \${state.y - 2}px)\`);
    place();
    root.querySelector(".caption").textContent = state.caption;
    addEventListener("mousemove", (event) => {
      state.x = event.clientX; state.y = event.clientY; place();
    }, true);
    addEventListener("mousedown", (event) => {
      const ring = document.createElement("div");
      ring.className = "ring";
      ring.style.left = event.clientX + "px";
      ring.style.top = event.clientY + "px";
      root.append(ring);
      setTimeout(() => ring.remove(), 450);
    }, true);
  };
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", mount);
  else mount();
  new MutationObserver(mount).observe(document, { childList: true, subtree: true });
})();
`;

/** The reel's recorder: frames and the track, both timed from its start. */
class Reel {
  readonly track: Track = {
    size: SIZE,
    theme: THEME,
    scenes: [],
    cursor: [],
    clicks: [],
    keys: [],
  };
  readonly frames: { file: string; t: number }[] = [];
  // The reel's own clock, in ms: it runs only inside a beat, for the beat's
  // declared length, so the timeline is the same in every run. Waiting for
  // the app (a request, a render) takes no time on it; the frames that arrive
  // meanwhile collapse onto one instant and the last of them is shown.
  private clock = 0;
  private beating: { real: number; from: number; ms: number } | null = null;
  private x = SIZE.width / 2;
  private y = SIZE.height / 2;

  constructor(
    private page: Page,
    private dir: string,
  ) {}

  /** The reel's time in seconds. */
  now() {
    const beat = this.beating;
    const ms = beat
      ? beat.from + Math.min(performance.now() - beat.real, beat.ms)
      : this.clock;
    return Math.round(ms) / 1000;
  }

  /** `ms` of reel time, spent on `run` (by default, simply waiting `ms`). */
  private async beat(ms: number, run = () => this.page.waitForTimeout(ms)) {
    this.beating = { real: performance.now(), from: this.clock, ms };
    await run();
    this.beating = null;
    this.clock += ms;
  }

  async record() {
    mkdirSync(join(this.dir, "frames"), { recursive: true });
    await this.page.screencast.start({
      size: SIZE,
      quality: 90,
      onFrame: ({ data }) => {
        const file = `frames/${String(this.frames.length).padStart(5, "0")}.jpg`;
        this.frames.push({ file, t: this.now() });
        writeFileSync(join(this.dir, file), data);
      },
    });
    await this.page.mouse.move(this.x, this.y);
  }

  async stop() {
    await this.page.screencast.stop();
    const last = this.track.scenes.at(-1);
    if (last) last.end = this.now();
    writeFileSync(
      join(this.dir, "frames.json"),
      JSON.stringify({ end: this.now(), frames: this.frames }),
    );
    writeFileSync(
      join(this.dir, "track.json"),
      JSON.stringify(this.track, null, 1) + "\n",
    );
  }

  /** Begin a scene: its caption, and where the action is. */
  async scene(caption: string, focus: Locator) {
    const last = this.track.scenes.at(-1);
    if (last) last.end = this.now();
    this.track.scenes.push({ caption, start: this.now(), focus: [] });
    await this.page.evaluate((text) => {
      window.__reel.caption = text;
      const node = document.querySelector("#reel .caption");
      if (node) node.textContent = text;
    }, caption);
    await this.focus(focus);
  }

  /** The focal region of the current scene from now on. */
  async focus(target: Locator) {
    const box = await target.boundingBox();
    if (!box) throw Error("The focal region is not on screen.");
    const rect = {
      x: Math.round(box.x),
      y: Math.round(box.y),
      width: Math.round(Math.min(box.width, SIZE.width - box.x)),
      height: Math.round(Math.min(box.height, SIZE.height - box.y)),
    };
    this.track.scenes.at(-1)!.focus.push({ t: this.now(), rect });
  }

  /** Glide the cursor to the middle of `target` (or a point in it). */
  async move(target: Locator, at?: { x: number; y: number }) {
    await target.scrollIntoViewIfNeeded();
    const box = (await target.boundingBox())!;
    const x = box.x + (at ? at.x : box.width / 2);
    const y = box.y + (at ? at.y : box.height / 2);
    const distance = Math.hypot(x - this.x, y - this.y);
    const steps = Math.max(8, Math.min(24, Math.round(distance / 30)));
    const [fromX, fromY] = [this.x, this.y];
    for (let step = 1; step <= steps; step++) {
      const p = step / steps;
      const ease = p < 0.5 ? 2 * p * p : 1 - (-2 * p + 2) ** 2 / 2;
      this.x = fromX + (x - fromX) * ease;
      this.y = fromY + (y - fromY) * ease;
      this.track.cursor.push({
        t: this.now(),
        x: Math.round(this.x),
        y: Math.round(this.y),
      });
      await this.beat(33, async () => {
        await this.page.mouse.move(this.x, this.y);
        await this.page.waitForTimeout(16);
      });
    }
  }

  async click(target: Locator, at?: { x: number; y: number }) {
    await this.move(target, at);
    await this.pause(120);
    this.track.clicks.push({
      t: this.now(),
      x: Math.round(this.x),
      y: Math.round(this.y),
    });
    await this.page.mouse.down();
    await this.page.mouse.up();
  }

  /** Press a key and show it as a chip; `label` is what the chip reads. */
  async press(key: string, label: string) {
    this.track.keys.push({ t: this.now(), key, label });
    await this.page.evaluate((text) => {
      const keys = document.querySelector("#reel .keys");
      if (!keys) return;
      const chip = document.createElement("span");
      chip.className = "key";
      chip.textContent = text;
      keys.append(chip);
      setTimeout(() => (chip.style.opacity = "0"), 1150);
      setTimeout(() => chip.remove(), 1450);
    }, label);
    await this.pause(200);
    await this.page.keyboard.press(key);
    // The screen's answer to the key, off the clock: it starts the next beat.
    await this.page.waitForTimeout(250);
  }

  /** The end card: lines of text, then the command, then the address. */
  async endCard(title: string, line: string, command: string, slug: string) {
    await this.page.evaluate(
      ({ title, line, command, slug }) => {
        const card = document.querySelector("#reel .card")!;
        card.innerHTML = "<h2></h2><p></p><code></code><p></p>";
        const [first, last] = card.querySelectorAll("p");
        card.querySelector("h2")!.textContent = title;
        first.textContent = line;
        card.querySelector("code")!.textContent = command;
        last.textContent = slug;
        document.querySelector("#reel .caption")!.textContent = "";
        card.classList.add("on");
      },
      { title, line, command, slug },
    );
  }

  /** Hold for `ms` of reel time while the page goes on. */
  pause(ms: number) {
    return this.beat(ms);
  }
}

declare global {
  interface Window {
    __reel: { x: number; y: number; caption: string };
  }
}

/**
 * The screen's requests are answered, its skeleton rows are gone and its
 * transitions have ended, so the next beat starts on the finished screen in
 * every run. It is off the reel's clock: it takes no time in the reel.
 */
async function settled(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".ui-skeleton-rows")).toHaveCount(0);
  await page.waitForTimeout(300);
}

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
  const reel = new Reel(page, OUT!);
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
  const employer = main.getByRole("link", { name: /Apply on employer/ });
  await reel.focus(employer);
  const popup = page.context().waitForEvent("page");
  await reel.click(employer);
  await (await popup).close();
  await page.bringToFront();
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
