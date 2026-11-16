// The recorder of the video capture (video.spec.ts): the page's screencast as
// JPEG frames, timed by the reel's own clock, and the track of scenes, focal
// regions, cursor, clicks, keys and anchors.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expectPdfsShown } from "../scripts/capture.mjs";
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
  // Named DOM rectangles (page pixels) a video anchors to: a close-up's
  // target, the words an underline marks (Reel.anchor).
  anchors?: { name: string; t: number; rects: Rect[] }[];
  // The page's text at the end, for a privacy check of the footage.
  text?: string;
};

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
  private scale: number;
  private quality: number;

  /**
   * The frames are the bare dashboard: the video draws the cursor, keys and
   * captions itself from the track. `scale` is the device scale factor of the
   * page, so the frames are that many times larger.
   */
  constructor(
    private page: Page,
    private dir: string,
    options: {
      size?: { width: number; height: number };
      theme?: string;
      scale?: number;
      quality?: number;
      /** Where the pointer rests when the recording starts. */
      cursor?: { x: number; y: number };
    } = {},
  ) {
    this.size = options.size ?? SIZE;
    this.scale = options.scale ?? 1;
    this.quality = options.quality ?? 90;
    this.track.size = this.size;
    this.track.theme = options.theme ?? "light";
    if (this.scale !== 1) this.track.scale = this.scale;
    this.x = options.cursor?.x ?? this.size.width / 2;
    this.y = options.cursor?.y ?? this.size.height / 2;
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

  /** Record named rectangles (page pixels) at this moment of the reel. */
  anchor(name: string, rects: Rect[]) {
    (this.track.anchors ??= []).push({
      name,
      t: this.now(),
      rects: rects.map((r) => ({
        x: Math.round(r.x),
        y: Math.round(r.y),
        width: Math.round(r.width),
        height: Math.round(r.height),
      })),
    });
  }

  /**
   * Glide the cursor to the middle of `target` (or a point in it), in `ms`
   * of reel time (by default, by the distance).
   */
  async move(target: Locator, at?: { x: number; y: number }, ms?: number) {
    await target.scrollIntoViewIfNeeded();
    const box = (await target.boundingBox())!;
    const x = box.x + (at ? at.x : box.width / 2);
    const y = box.y + (at ? at.y : box.height / 2);
    const distance = Math.hypot(x - this.x, y - this.y);
    const steps = ms
      ? Math.max(2, Math.round(ms / 33))
      : Math.max(8, Math.min(24, Math.round(distance / 30)));
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

  async click(target: Locator, at?: { x: number; y: number }, ms?: number) {
    await this.move(target, at, ms);
    await this.pause(120);
    this.track.clicks.push({
      t: this.now(),
      x: Math.round(this.x),
      y: Math.round(this.y),
    });
    await this.page.mouse.down();
    await this.page.mouse.up();
  }

  /** Press a key; `label` is what the video's key chip reads. */
  async press(key: string, label: string) {
    this.track.keys.push({ t: this.now(), key, label });
    await this.pause(200);
    await this.page.keyboard.press(key);
    // The screen's answer to the key, off the clock: it starts the next beat.
    await this.page.waitForTimeout(250);
  }

  /** Hold for `ms` of reel time while the page goes on. */
  pause(ms: number) {
    return this.beat(ms);
  }
}

/**
 * The screen's requests are answered, its skeleton rows are gone, its
 * transitions have ended and its PDFs are drawn, so the next beat starts on
 * the finished screen in every run. It is off the reel's clock: it takes no
 * time in the reel.
 */
export async function settled(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".ui-skeleton-rows")).toHaveCount(0);
  await page.waitForTimeout(300);
  await expectPdfsShown(page);
}
