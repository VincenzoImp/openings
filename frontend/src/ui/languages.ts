// The languages a person can say they speak, shared by Setup and Preferences.
// What is stored is the ISO 639-1 code; any code can be recorded ("Other
// language…"), even one the posting-language detector does not know. Names
// come from the browser (Intl.DisplayNames, in English). No React and no
// imports: tested directly (tests/languages.test.mjs).

const names = new Intl.DisplayNames(["en"], {
  type: "language",
  fallback: "none",
});

/** A two-letter code's English name, or nothing for a code no language has. */
const displayName = (code: string) =>
  /^[a-z]{2}$/.test(code) ? names.of(code) : undefined;

/** A code's English name: "de" is German, "yo" Yoruba; else the code itself. */
export const languageName = (code: string) =>
  displayName(code) ?? code.toUpperCase();

/** The languages offered by name, alphabetically: [code, name]. */
export const LANGUAGES: [string, string][] = (
  "ar bn bg ca zh hr cs da nl en et tl fi fr de el he hi hu id it ja ko lv lt " +
  "ms no fa pl pt ro ru sr sk sl es sw sv ta th tr uk ur vi"
)
  .split(" ")
  .map((code): [string, string] => [code, languageName(code)])
  .sort(([, one], [, other]) => one.localeCompare(other));

/**
 * The languages whose requirement a posting is read for ("German required"),
 * as backend/openings/language_signals.py recognises them. A posting that
 * requires another language is never hidden.
 */
export const REQUIREMENT_LANGUAGES =
  "en de fr it es nl pt pl sv da no fi cs ru ja zh ar tr ko".split(" ");

/** What hiding the jobs that require another language can read. */
export const REQUIREMENT_LIMIT = `Jobs reads requirements in ${REQUIREMENT_LANGUAGES.length} languages; one requiring another is never hidden.`;

/**
 * What a person typed as another language, as a code to store: a two-letter
 * ISO 639-1 code ("yo") or a language's English name ("Yoruba"). Null when it
 * is neither.
 */
export function languageCode(typed: string) {
  const value = typed.trim().toLowerCase();
  if (value.length < 3) return displayName(value) ? value : null;
  for (let first = 97; first <= 122; first += 1)
    for (let second = 97; second <= 122; second += 1) {
      const code = String.fromCharCode(first, second);
      if (displayName(code)?.toLowerCase() === value) return code;
    }
  return null;
}
