import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

function luminance(hex) {
  const [r, g, b] = [1, 3, 5]
    .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function ratio(a, b) {
  const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (high + 0.05) / (low + 0.05);
}

// The design system of the new dashboard (src/ui/tokens.css, design direction
// 21): the 43 pairs of the direction in each theme (86 in all), held to WCAG
// AA. Text needs 4.5:1; control boundaries and the focus ring need 3:1.
const ui = readFileSync(
  new URL("../src/ui/tokens.css", import.meta.url),
  "utf8",
);
function uiBlock(selector) {
  const from = ui.indexOf(selector + " {");
  assert.notEqual(from, -1, `src/ui/tokens.css has no ${selector} block`);
  const body = ui.slice(from, ui.indexOf("}", from));
  return Object.fromEntries(
    [...body.matchAll(/(--[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)].map((m) => [
      m[1],
      m[2].toLowerCase(),
    ]),
  );
}
const uiLight = uiBlock(":root");
const uiDark = uiBlock(':root[data-theme="dark"]');
const uiSystemDark = uiBlock(':root:not([data-theme="light"])');
const uiThemes = {
  light: { ...uiLight, "--focus": uiLight["--accent"] },
  dark: { ...uiLight, ...uiDark, "--focus": uiDark["--accent"] },
};

test("src/ui: the system dark theme equals the chosen dark theme", () => {
  assert.deepEqual(uiSystemDark, uiDark);
  for (const token of Object.keys(uiLight))
    assert.ok(token in uiDark, `${token} has no dark value`);
});

const UI_SURFACES = [
  "--bg",
  "--bg-subtle",
  "--surface",
  "--hover",
  "--selected",
];
const UI_PAIRS = [
  ...UI_SURFACES.flatMap((surface) => [
    ["--text", surface, 4.5],
    ["--text-2", surface, 4.5],
    ["--text-3", surface, 4.5],
    ["--accent-text", surface, 4.5],
    ["--control", surface, 3],
    ["--focus", surface, 3],
  ]),
  ["--on-primary", "--primary", 4.5],
  ["--on-accent", "--accent", 4.5],
  ["--accent-text", "--accent-soft", 4.5],
  ["--success", "--success-soft", 4.5],
  ["--warning", "--warning-soft", 4.5],
  ["--danger", "--danger-soft", 4.5],
  ["--success", "--bg", 4.5],
  ["--warning", "--bg", 4.5],
  ["--danger", "--bg", 4.5],
  ["--success", "--surface", 4.5],
  ["--warning", "--surface", 4.5],
  ["--danger", "--surface", 4.5],
  ["--danger", "--hover", 4.5],
];

test("src/ui: the design direction's 43 pairs per theme are checked", () => {
  assert.equal(UI_PAIRS.length, 43);
});

for (const [theme, tokens] of Object.entries(uiThemes))
  test(`src/ui tokens meet WCAG AA in the ${theme} theme`, () => {
    const failures = [];
    // Beyond the direction: the label of the permanent-delete button.
    for (const [text, background, min] of [
      ...UI_PAIRS,
      ["--on-danger", "--danger", 4.5],
    ]) {
      const value = ratio(tokens[text], tokens[background]);
      if (value < min - 0.005)
        failures.push(`${text} on ${background} is ${value.toFixed(2)}:1`);
    }
    assert.deepEqual(failures, []);
  });
