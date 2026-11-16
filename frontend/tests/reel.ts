// The reel recorder (`npm run reel`, reel.spec.ts) and the video capture
// (video.spec.ts): the page's screencast as JPEG frames, timed by the reel's
// own clock, and the track of scenes, focal regions, cursor, clicks and keys.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, type Locator, type Page } from "./fixtures";

export const SIZE = { width: 1280, height: 800 };

export type Rect = { x: number; y: number; width: number; height: number };
export type Track = {
  size: typeof SIZE;
  // Frame pixels per page pixel.
  scale?: number;
  theme: string;
  scenes: {
    id?: string;
    caption: string;
    start: number;
    end?: number;
    focus: { t: number; rect: Rect }[];
  }[];
  cursor: { t: number; x: number; y: number }[];
  clicks: { t: number; x: number; y: number }[];
  keys: { t: number; key: string; label: string }[];
  // Stretches recorded in real time (Reel.live), with the wall clock at their
  // start, to line them up with another recording of the same moments.
  live?: { start: number; end: number; epochMs: number }[];
};

// The overlay layer, installed in every document: a cursor that follows the
// mouse, a ring on each press, key chips at the top right, the caption at the
// bottom left and the end card. It never takes a pointer event.
export const OVERLAY = `
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
export class Reel {
  readonly track: Track = {
    size: SIZE,
    theme: "light",
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
  private x: number;
  private y: number;
  private size: { width: number; height: number };
  private overlay: boolean;
  private scale: number;
  private quality: number;

  /**
   * `overlay: false` records the bare dashboard, for a video that draws the
   * cursor, keys and captions itself from the track; `scale` is the device
   * scale factor of the page, so the frames are that many times larger.
   */
  constructor(
    private page: Page,
    private dir: string,
    options: {
      size?: { width: number; height: number };
      theme?: string;
      overlay?: boolean;
      scale?: number;
      quality?: number;
    } = {},
  ) {
    this.size = options.size ?? SIZE;
    this.overlay = options.overlay ?? true;
    this.scale = options.scale ?? 1;
    this.quality = options.quality ?? 90;
    this.track.size = this.size;
    this.track.theme = options.theme ?? "light";
    if (this.scale !== 1) this.track.scale = this.scale;
    this.x = this.size.width / 2;
    this.y = this.size.height / 2;
  }

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
      size: {
        width: this.size.width * this.scale,
        height: this.size.height * this.scale,
      },
      quality: this.quality,
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
  async scene(caption: string, focus: Locator, id?: string) {
    const last = this.track.scenes.at(-1);
    if (last) last.end = this.now();
    this.track.scenes.push({ id, caption, start: this.now(), focus: [] });
    if (this.overlay)
      await this.page.evaluate((text) => {
        window.__reel.caption = text;
        const node = document.querySelector("#reel .caption");
        if (node) node.textContent = text;
      }, caption);
    await this.focus(focus);
  }

  /** The focal region of the current scene from now on. */
  async focus(target: Locator) {
    await target.scrollIntoViewIfNeeded();
    const box = await target.boundingBox();
    if (!box) throw Error("The focal region is not on screen.");
    // The part of it on screen.
    const x = Math.max(box.x, 0);
    const y = Math.max(box.y, 0);
    const rect = {
      x: Math.round(x),
      y: Math.round(y),
      width: Math.round(Math.min(box.x + box.width, this.size.width) - x),
      height: Math.round(Math.min(box.y + box.height, this.size.height) - y),
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
    if (this.overlay)
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

  /**
   * Record in real time until `run` ends: the page's own changes (a list that
   * polls the server, say), timed by the wall clock, which the track keeps so
   * the stretch lines up with another recording of the same moments.
   */
  async live(run: () => Promise<void>) {
    const from = this.clock;
    const epochMs = Date.now();
    const real = performance.now();
    this.beating = { real, from, ms: Infinity };
    await run();
    const ms = Math.round(performance.now() - real);
    this.beating = null;
    this.clock += ms;
    (this.track.live ??= []).push({
      start: from / 1000,
      end: this.clock / 1000,
      epochMs,
    });
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
export async function settled(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".ui-skeleton-rows")).toHaveCount(0);
  await page.waitForTimeout(300);
}
