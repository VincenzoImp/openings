import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of the source files; this module has no React.
const languages = await import("../src/ui/languages.ts");

test("Setup and Preferences offer one list of languages", () => {
  const codes = languages.LANGUAGES.map(([code]) => code);
  assert.deepEqual(codes, [
    "ar",
    "bn",
    "bg",
    "ca",
    "zh",
    "hr",
    "cs",
    "da",
    "nl",
    "en",
    "et",
    "tl",
    "fi",
    "fr",
    "de",
    "el",
    "he",
    "hi",
    "hu",
    "id",
    "it",
    "ja",
    "ko",
    "lv",
    "lt",
    "ms",
    "no",
    "fa",
    "pl",
    "pt",
    "ro",
    "ru",
    "sr",
    "sk",
    "sl",
    "es",
    "sw",
    "sv",
    "ta",
    "th",
    "tr",
    "uk",
    "ur",
    "vi",
  ]);
  const names = languages.LANGUAGES.map(([, name]) => name);
  assert.deepEqual(names, [...names].sort());
  // Every language the requirement detector reads is in it.
  for (const code of languages.REQUIREMENT_LANGUAGES)
    assert.ok(codes.includes(code), code);
});

test("any other language is recorded by its name or its code", () => {
  assert.equal(languages.languageCode("yo"), "yo");
  assert.equal(languages.languageCode(" Yoruba "), "yo");
  assert.equal(languages.languageCode("german"), "de");
  assert.equal(languages.languageCode("zz"), null);
  assert.equal(languages.languageCode("Klingon"), null);
  assert.equal(languages.languageName("de"), "German");
  assert.equal(languages.languageName("yo"), "Yoruba");
  assert.equal(languages.languageName("zz"), "ZZ");
});
