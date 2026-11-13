// `npm run screenshots [-- --docs] [playwright options]`: run the screenshots
// project (tests/screenshots.spec.ts). Without --docs the images of every
// screen go to frontend/screenshots/, replacing the previous set; with --docs
// the images the user documentation embeds go to docs/images/.
import { spawnSync } from "node:child_process";
import { rmSync } from "node:fs";

const args = process.argv.slice(2);
const docs = args.includes("--docs");
if (!docs)
  rmSync(new URL("../screenshots", import.meta.url), {
    recursive: true,
    force: true,
  });
const result = spawnSync(
  "npx",
  [
    "playwright",
    "test",
    "--project=screenshots",
    ...args.filter((arg) => arg !== "--docs"),
  ],
  {
    stdio: "inherit",
    env: {
      ...process.env,
      ...(docs ? { OPENINGS_SCREENSHOTS_DOCS: "1" } : {}),
    },
  },
);
process.exit(result.status ?? 1);
