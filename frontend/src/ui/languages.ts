// The languages a person can say they speak, shared by Setup and Preferences.
// What is stored is the ISO 639-1 code; any code can be recorded ("Other
// language…"), even one the posting-language detector does not know. No React
// and no imports: tested directly (tests/languages.test.mjs).

/** The languages offered by name, alphabetically. */
export const LANGUAGES: [string, string][] = [
  ["ar", "Arabic"],
  ["bn", "Bengali"],
  ["bg", "Bulgarian"],
  ["ca", "Catalan"],
  ["zh", "Chinese"],
  ["hr", "Croatian"],
  ["cs", "Czech"],
  ["da", "Danish"],
  ["nl", "Dutch"],
  ["en", "English"],
  ["et", "Estonian"],
  ["tl", "Filipino"],
  ["fi", "Finnish"],
  ["fr", "French"],
  ["de", "German"],
  ["el", "Greek"],
  ["he", "Hebrew"],
  ["hi", "Hindi"],
  ["hu", "Hungarian"],
  ["id", "Indonesian"],
  ["it", "Italian"],
  ["ja", "Japanese"],
  ["ko", "Korean"],
  ["lv", "Latvian"],
  ["lt", "Lithuanian"],
  ["ms", "Malay"],
  ["no", "Norwegian"],
  ["fa", "Persian"],
  ["pl", "Polish"],
  ["pt", "Portuguese"],
  ["ro", "Romanian"],
  ["ru", "Russian"],
  ["sr", "Serbian"],
  ["sk", "Slovak"],
  ["sl", "Slovenian"],
  ["es", "Spanish"],
  ["sw", "Swahili"],
  ["sv", "Swedish"],
  ["ta", "Tamil"],
  ["th", "Thai"],
  ["tr", "Turkish"],
  ["uk", "Ukrainian"],
  ["ur", "Urdu"],
  ["vi", "Vietnamese"],
];

const NAMES = new Map(LANGUAGES);

/**
 * The languages whose requirement a posting is read for ("German required"),
 * as backend/openings/language_signals.py recognises them. A posting that
 * requires another language is never hidden.
 */
export const REQUIREMENT_LANGUAGES = [
  "en",
  "de",
  "fr",
  "it",
  "es",
  "nl",
  "pt",
  "pl",
  "sv",
  "da",
  "no",
  "fi",
  "cs",
  "ru",
  "ja",
  "zh",
  "ar",
  "tr",
  "ko",
];

/** What hiding the jobs that require another language can read. */
export const REQUIREMENT_LIMIT = `Jobs reads a language requirement in ${REQUIREMENT_LANGUAGES.length} languages; a posting that requires any other is never hidden.`;

let names: Intl.DisplayNames | null | undefined;

function displayName(code: string) {
  if (names === undefined)
    try {
      names = new Intl.DisplayNames(["en"], {
        type: "language",
        fallback: "none",
      });
    } catch {
      names = null;
    }
  try {
    return names?.of(code);
  } catch {
    return undefined;
  }
}

/** A code's English name: "de" is German, "yo" Yoruba; else the code itself. */
export function languageName(code: string) {
  return NAMES.get(code) ?? displayName(code) ?? code.toUpperCase();
}

/**
 * What a person typed as another language, as a code to store: a two-letter
 * ISO 639-1 code ("yo") or a language's English name ("Yoruba"). Null when it
 * is neither.
 */
export function languageCode(typed: string) {
  const value = typed.trim().toLowerCase();
  if (/^[a-z]{2}$/.test(value)) return displayName(value) ? value : null;
  const named = LANGUAGES.find(([, name]) => name.toLowerCase() === value);
  if (named) return named[0];
  for (let first = 97; first <= 122; first += 1)
    for (let second = 97; second <= 122; second += 1) {
      const code = String.fromCharCode(first, second);
      if (displayName(code)?.toLowerCase() === value) return code;
    }
  return null;
}
