// `npm run reel [-- --dark] [playwright options]`: build the dashboard, record
// the README's demo reel (tests/reel.spec.ts) against it and encode it with
// ffmpeg: docs/images/demo.gif (or demo-dark.gif) at 12 fps with a palette
// made for it, and an MP4 master with the frames, the frame times and the
// track (scenes, focal regions, cursor, clicks and keys) in frontend/reel/,
// which Git ignores. Fails when a GIF is larger than LIMIT.
//
// Needs ffmpeg on PATH and the installed Playwright (`npm ci` first; see
// screenshots.mjs for why npx's own copy does not do). Re-render after every
// change to the screens it shows.
import { spawnSync } from "node:child_process";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { fileURLToPath } from "node:url";

const LIMIT = 5 * 1024 * 1024;
const FPS = 12;
const root = fileURLToPath(new URL("..", import.meta.url));
const run = (command, args, env = process.env) =>
  spawnSync(command, args, { cwd: root, stdio: "inherit", env }).status ?? 1;

if (!existsSync(new URL("../node_modules/@playwright/test", import.meta.url))) {
  console.error(
    "Playwright is not installed. Run `npm ci` in frontend/ first.",
  );
  process.exit(2);
}
if (spawnSync("ffmpeg", ["-version"]).status !== 0) {
  console.error("ffmpeg is not on PATH. Install it first.");
  process.exit(2);
}
// Always built first: a reel of an older build would go unnoticed.
const built = run("npm", ["run", "build"]);
if (built) process.exit(built);

const args = process.argv.slice(2);
const theme = args.includes("--dark") ? "dark" : "light";
const name = theme === "dark" ? "demo-dark" : "demo";
const reel = fileURLToPath(new URL("../reel/", import.meta.url));
const dir = `${reel}${theme}/`;
const gif = fileURLToPath(
  new URL(`../../docs/images/${name}.gif`, import.meta.url),
);
rmSync(dir, { recursive: true, force: true });
mkdirSync(dir, { recursive: true });

const recorded = run(
  "npx",
  [
    "--no-install",
    "playwright",
    "test",
    "--project=reel",
    ...args.filter((arg) => arg !== "--dark"),
  ],
  { ...process.env, OPENINGS_REEL_DIR: dir, OPENINGS_REEL_THEME: theme },
);
if (recorded) process.exit(recorded);

// The screencast sends a frame only when the page changes: each frame lasts
// until the next one, the last until the end of the recording.
const { end, frames } = JSON.parse(readFileSync(`${dir}frames.json`, "utf8"));
if (!frames.length) {
  console.error("The recording has no frames.");
  process.exit(1);
}
const list = frames.map(({ file, t }, index) => {
  const next = index + 1 < frames.length ? frames[index + 1].t : end;
  return `file '${file}'\nduration ${Math.max(next - t, 0.001).toFixed(3)}`;
});
// The concat demuxer takes the last file's duration only when it is repeated.
list.push(`file '${frames.at(-1).file}'`);
writeFileSync(`${dir}frames.txt`, list.join("\n") + "\n");

const input = ["-f", "concat", "-safe", "0", "-i", `${dir}frames.txt`];
const ffmpeg = (...rest) =>
  run("ffmpeg", [
    "-hide_banner",
    "-loglevel",
    "error",
    "-y",
    ...input,
    ...rest,
  ]);
const master = `${reel}${name}.mp4`;
if (
  ffmpeg(
    "-vf",
    `fps=${FPS}`,
    "-c:v",
    "libx264",
    "-preset",
    "slow",
    "-crf",
    "16",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
    master,
  ) ||
  ffmpeg(
    "-filter_complex",
    `fps=${FPS},split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];` +
      "[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
    "-loop",
    "0",
    gif,
  )
)
  process.exit(1);
copyFileSync(`${dir}track.json`, `${reel}${name}.track.json`);

const size = statSync(gif).size;
const mb = (size / 1024 / 1024).toFixed(2);
console.log(`${gif}: ${mb} MB, ${end.toFixed(1)} s`);
console.log(`Master and track: ${master}, ${reel}${name}.track.json`);
if (size > LIMIT) {
  console.error(`The GIF is larger than ${LIMIT / 1024 / 1024} MB.`);
  process.exit(1);
}
