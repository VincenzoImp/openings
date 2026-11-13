import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// The contrast of every token on the backgrounds it is used on, computed from
// src/design/tokens.css in both themes and held to WCAG AA.
const css = readFileSync(
  new URL("../src/design/tokens.css", import.meta.url),
  "utf8",
);

function block(selector) {
  const start = css.indexOf(selector + " {");
  assert.notEqual(start, -1, `tokens.css has no ${selector} block`);
  const body = css.slice(start, css.indexOf("}", start));
  return Object.fromEntries(
    [...body.matchAll(/(--[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)].map((m) => [
      m[1],
      m[2].toLowerCase(),
    ]),
  );
}
const light = block(":root");
const themes = {
  light,
  dark: { ...light, ...block(':root[data-theme="dark"]') },
};

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

const surfaces = ["--bg", "--surface", "--card"];
// Where each token is used. Text needs 4.5:1; a control boundary needs 3:1.
const pairs = {
  "--ink": { on: surfaces, min: 4.5 },
  "--ink-2": { on: surfaces, min: 4.5 },
  // Captions: surface and card only, never the shell or a soft background.
  "--ink-3": { on: ["--surface", "--card"], min: 4.5 },
  "--accent": { on: [...surfaces, "--accent-soft"], min: 4.5 },
  "--ready": { on: [...surfaces, "--ready-soft"], min: 4.5 },
  "--attention": { on: [...surfaces, "--attention-soft"], min: 4.5 },
  "--danger": { on: [...surfaces, "--danger-soft"], min: 4.5 },
  "--info": { on: [...surfaces, "--info-soft"], min: 4.5 },
  "--agent": { on: [...surfaces, "--agent-soft"], min: 4.5 },
  // Buttons and inputs sit on surface, card, hover or the soft accent.
  "--control": {
    on: ["--surface", "--card", "--hover", "--accent-soft"],
    min: 3,
  },
};

for (const [token, { on, min }] of Object.entries(pairs))
  for (const [theme, tokens] of Object.entries(themes))
    test(`${token} in the ${theme} theme meets ${min}:1`, () => {
      for (const background of on) {
        const value = ratio(tokens[token], tokens[background]);
        assert.ok(
          value >= min - 0.05,
          `${token} on ${background} is ${value.toFixed(2)}:1, below ${min}:1`,
        );
      }
    });

for (const [theme, tokens] of Object.entries(themes)) {
  test(`text on filled and soft backgrounds is readable in the ${theme} theme`, () => {
    const check = (text, background) => {
      const value = ratio(tokens[text], tokens[background]);
      assert.ok(
        value >= 4.5,
        `${text} on ${background} is ${value.toFixed(2)}:1`,
      );
    };
    check("--on-accent", "--accent"); // primary button
    check("--card", "--ink"); // toast
    check("--card", "--danger"); // error toast
    // Secondary text is the one used on soft backgrounds and on hover.
    for (const background of [
      "--hover",
      "--accent-soft",
      "--ready-soft",
      "--attention-soft",
      "--danger-soft",
      "--info-soft",
      "--agent-soft",
    ]) {
      check("--ink", background);
      check("--ink-2", background);
    }
  });
}
