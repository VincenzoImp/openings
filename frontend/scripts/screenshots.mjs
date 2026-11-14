// `npm run screenshots [-- --docs] [playwright options]`: run the screenshots
// project (tests/screenshots.spec.ts) against the built dashboard. Without
// --docs the images of every screen go to frontend/screenshots/, replacing the
// previous set; with --docs the images the user documentation embeds go to
// docs/images/.
//
// The installed Playwright runs the tests (`npm ci` first): a Playwright that
// npx would download is another copy of the test runner, and the spec's
// `test.describe()` then fails with "did not expect test.describe() to be
// called here". The server serves frontend/dist, so the dashboard is built
// first when it is missing.
import { spawnSync } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const run = (command, args, env = process.env) =>
  spawnSync(command, args, { cwd: root, stdio: "inherit", env }).status ?? 1;

if (!existsSync(new URL("../node_modules/@playwright/test", import.meta.url))) {
  console.error(
    "Playwright is not installed. Run `npm ci` in frontend/ first.",
  );
  process.exit(2);
}
if (!existsSync(new URL("../dist/index.html", import.meta.url))) {
  const built = run("npm", ["run", "build"]);
  if (built) process.exit(built);
}

const args = process.argv.slice(2);
const docs = args.includes("--docs");
if (!docs)
  rmSync(new URL("../screenshots", import.meta.url), {
    recursive: true,
    force: true,
  });
process.exit(
  run(
    "npx",
    [
      "--no-install",
      "playwright",
      "test",
      "--project=screenshots",
      ...args.filter((arg) => arg !== "--docs"),
    ],
    { ...process.env, ...(docs ? { OPENINGS_SCREENSHOTS_DOCS: "1" } : {}) },
  ),
);
