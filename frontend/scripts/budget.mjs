// Size budgets of the built dashboard. Reads the Vite manifest of
// `npm run build`, prints a table and exits with 1 when a budget is exceeded.
//
//   first screen   JavaScript needed to show the home screen        85 kB
//                  (React, Query and the shell included)
//   lazy chunk     JavaScript a screen or an overlay adds           30 kB
//   all JS         every script the dashboard can load             160 kB
//   stylesheet     every stylesheet of the dashboard together       20 kB
//
// Interim: the first screen still carries the old data layer and component
// helpers (src/state.tsx, src/api.ts, src/design) that Today and the other
// old screens need, and the old screens weigh on all JS. Until they are
// rebuilt (#222–#227) the budgets are 120 kB and 210 kB; #228 deletes the old
// code and sets them back to 85 kB and 160 kB.
//
// Sizes are gzip (level 9) in kB of 1000 bytes, as Vite reports them. The
// design system gallery (ui.html) is not part of the dashboard: its size is
// reported for information and held to no budget.
import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";

const KB = 1000;
const BUDGET = {
  first: 120 * KB, // 85 kB once #228 deletes the old screens' code
  later: 30 * KB,
  all: 210 * KB, // 160 kB once #228 deletes the old screens' code
  css: 20 * KB,
};
const HOME = "src/screens/today/Today.tsx";

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

const ENTRY = "index.html";
const GALLERY = "ui.html";
const entry = manifest[ENTRY]?.isEntry ? ENTRY : null;
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
// The dashboard: the entry and every chunk it can load, without the gallery.
function reachable(key, seen = new Set()) {
  if (seen.has(key)) return seen;
  seen.add(key);
  const chunk = manifest[key];
  for (const next of [
    ...(chunk.imports || []),
    ...(chunk.dynamicImports || []),
  ])
    reachable(next, seen);
  return seen;
}
const dashboard = reachable(entry);
const screens = [...dashboard]
  .filter((key) => manifest[key].isDynamicEntry && key !== HOME)
  .sort();
for (const key of screens) {
  const own = scripts(closure(key)).filter((file) => !firstFiles.has(file));
  add(
    key.startsWith("src/pages/")
      ? `Screen ${key.replace(/^src\/pages\//, "").replace(/\.tsx$/, "")}`
      : `Chunk ${key.replace(/^src\//, "").replace(/\.tsx?$/, "")}`,
    total(own),
    BUDGET.later,
  );
}
const everything = new Set(scripts(dashboard));
add(
  "All JavaScript",
  total([...everything]),
  BUDGET.all,
  `${everything.size} files`,
);
const styles = new Set(
  [...dashboard].flatMap((key) => manifest[key].css || []),
);
add("Stylesheet", total([...styles]), BUDGET.css, `${styles.size} files`);

const info = [];
if (manifest[GALLERY]) {
  const gallery = closure(GALLERY);
  const own = scripts(gallery).filter((file) => !firstFiles.has(file));
  info.push(["Gallery JavaScript (own)", total(own)]);
  const css = [
    ...new Set([...gallery].flatMap((key) => manifest[key].css || [])),
  ];
  info.push(["Gallery stylesheet", total(css)]);
}

const kb = (bytes) => (bytes / KB).toFixed(2).padStart(7) + " kB";
const width = Math.max(...rows.map((row) => row.name.length));
console.log(`${"".padEnd(width)}      gzip      budget`);
for (const row of rows)
  console.log(
    `${row.name.padEnd(width)}  ${kb(row.size)}  ${kb(row.limit)}  ${
      row.ok ? "ok" : "OVER"
    }${row.note ? `  (${row.note})` : ""}`,
  );
for (const [name, size] of info)
  console.log(`${name.padEnd(width)}  ${kb(size)}  (information)`);
const over = rows.filter((row) => !row.ok);
if (over.length) {
  console.error(
    `\n${over.length} budget${over.length > 1 ? "s" : ""} exceeded: ${over
      .map((row) => row.name)
      .join(", ")}.`,
  );
  process.exit(1);
}
