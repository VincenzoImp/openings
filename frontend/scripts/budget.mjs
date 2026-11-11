// Size budgets of the built dashboard (docs/developer/dashboard-design.md,
// "Budgets"). Reads the Vite manifest of `npm run build`, prints a table and
// exits with 1 when a budget is exceeded.
//
//   first screen   JavaScript needed to show the home screen       110 kB
//   later screen   JavaScript a screen adds to what is loaded       40 kB
//   stylesheet     every stylesheet of the dashboard together       15 kB
//
// Sizes are gzip (level 9) in kB of 1000 bytes, as Vite reports them.
import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";

const KB = 1000;
const BUDGET = { first: 110 * KB, later: 40 * KB, css: 15 * KB };
const HOME = "src/pages/Overview.tsx";

// A temporary allowance for one old page that cannot meet its budget yet:
//   "src/pages/Name.tsx": { limit: 45 * KB, until: "stage 3", reason: "…" }
// Each entry names the stage of issue #135 that removes it. None is needed.
const ALLOWANCES = {};

const dist = new URL("../dist/", import.meta.url);
let manifest;
try {
  manifest = JSON.parse(
    readFileSync(new URL(".vite/manifest.json", dist), "utf8"),
  );
} catch {
  console.error("No build manifest. Run `npm run build` first.");
  process.exit(2);
}

const sizes = new Map();
function gzip(file) {
  if (!sizes.has(file))
    sizes.set(
      file,
      gzipSync(readFileSync(new URL(file, dist)), { level: 9 }).length,
    );
  return sizes.get(file);
}
/** A chunk and everything it imports statically, as manifest keys. */
function closure(key, seen = new Set()) {
  if (seen.has(key)) return seen;
  seen.add(key);
  for (const next of manifest[key].imports || []) closure(next, seen);
  return seen;
}
const scripts = (keys) =>
  [...keys].map((key) => manifest[key].file).filter((f) => f.endsWith(".js"));
const total = (files) => files.reduce((sum, file) => sum + gzip(file), 0);

const entry = Object.keys(manifest).find((key) => manifest[key].isEntry);
if (!entry || !manifest[HOME]) {
  console.error(`The manifest has no entry or no ${HOME}.`);
  process.exit(2);
}
const first = closure(HOME, closure(entry));
const firstFiles = new Set(scripts(first));

const rows = [];
const add = (name, size, limit, note = "") =>
  rows.push({ name, size, limit, note, ok: size <= limit });

add("First screen JavaScript", total([...firstFiles]), BUDGET.first);
const screens = Object.keys(manifest)
  .filter((key) => manifest[key].isDynamicEntry && key !== HOME)
  .sort();
for (const key of screens) {
  const own = scripts(closure(key)).filter((file) => !firstFiles.has(file));
  const allowance = ALLOWANCES[key];
  add(
    `Screen ${key.replace(/^src\/pages\//, "").replace(/\.tsx$/, "")}`,
    total(own),
    allowance?.limit ?? BUDGET.later,
    allowance ? `allowance until ${allowance.until}: ${allowance.reason}` : "",
  );
}
for (const key of Object.keys(ALLOWANCES))
  if (!manifest[key]?.isDynamicEntry) {
    console.error(`Allowance for ${key}, which is not a screen: remove it.`);
    process.exit(1);
  }
const styles = new Set(
  Object.values(manifest).flatMap((chunk) => chunk.css || []),
);
add("Stylesheet", total([...styles]), BUDGET.css, `${styles.size} files`);

const kb = (bytes) => (bytes / KB).toFixed(2).padStart(7) + " kB";
const width = Math.max(...rows.map((row) => row.name.length));
console.log(`${"".padEnd(width)}      gzip      budget`);
for (const row of rows)
  console.log(
    `${row.name.padEnd(width)}  ${kb(row.size)}  ${kb(row.limit)}  ${
      row.ok ? "ok" : "OVER"
    }${row.note ? `  (${row.note})` : ""}`,
  );
const over = rows.filter((row) => !row.ok);
if (over.length) {
  console.error(
    `\n${over.length} budget${over.length > 1 ? "s" : ""} exceeded: ${over
      .map((row) => row.name)
      .join(", ")}.`,
  );
  process.exit(1);
}
