// The first-run guide's model: its steps, and how "About you" maps onto the
// Profile, What I'm looking for and the spoken languages. No React and no
// imports: tested directly (tests/today.test.mjs).

export const STEPS = [
  { id: "about", label: "About you" },
  { id: "jobs", label: "Find jobs" },
  { id: "cv", label: "Your CV" },
  { id: "done", label: "Done" },
] as const;
export type StepId = (typeof STEPS)[number]["id"];

/** The step an address names; anything else is the first. */
export const stepOf = (value: string | null): StepId =>
  STEPS.find((step) => step.id === value)?.id ?? "about";

/** The languages offered first; their ISO 639-1 codes are what is stored. */
export const LANGUAGES: [string, string][] = [
  ["en", "English"],
  ["de", "German"],
  ["fr", "French"],
  ["it", "Italian"],
  ["es", "Spanish"],
  ["nl", "Dutch"],
  ["pt", "Portuguese"],
  ["pl", "Polish"],
];

export interface About {
  name: string;
  roles: string;
  where: string;
  languages: string[];
}

interface Item {
  text: string;
  scope?: "all" | "cv" | "letter" | null;
}
interface Section {
  section: string;
  version: number;
  items: Record<string, unknown>[];
}

// The statements step 1 writes, recognised again by their start.
const ROLES = "Roles: ";
const WHERE = "Where: ";

const lookingFor = (sections: Section[]) =>
  sections.find((section) => section.section === "looking_for");
const itemText = (item: Record<string, unknown>) => String(item.text ?? "");

/** What step 1 shows first: what the workspace already says. */
export function aboutFrom(
  profile: { name?: string },
  preferences: {
    sections: Section[];
    settings: { spoken_languages: string[] };
  },
): About {
  const items = lookingFor(preferences.sections)?.items ?? [];
  const find = (prefix: string) =>
    items
      .map(itemText)
      .find((text) => text.startsWith(prefix))
      ?.slice(prefix.length) ?? "";
  return {
    name: profile.name ?? "",
    roles: find(ROLES),
    where: find(WHERE),
    languages: [...preferences.settings.spoken_languages],
  };
}

/**
 * The writes step 1 needs: the name when it changed, What I'm looking for
 * with the roles and the place replaced or added (other statements kept), and
 * the languages when they changed. Null where nothing changes.
 */
export function aboutChanges(
  about: About,
  profile: { name?: string },
  preferences: {
    sections: Section[];
    settings: { spoken_languages: string[] };
  },
) {
  const name = about.name.trim();
  const section = lookingFor(preferences.sections);
  const before = (section?.items ?? []) as unknown as Item[];
  let items = [...before];
  for (const [prefix, value] of [
    [ROLES, about.roles.trim()],
    [WHERE, about.where.trim()],
  ] as const) {
    const index = items.findIndex((item) =>
      itemText(item as never).startsWith(prefix),
    );
    const next = value ? { text: prefix + value } : null;
    if (index >= 0) {
      if (next) items[index] = { ...items[index], ...next };
      else items = items.filter((_, at) => at !== index);
    } else if (next) items.push(next);
  }
  const same =
    items.length === before.length &&
    items.every((item, index) => item.text === before[index].text);
  const spoken = preferences.settings.spoken_languages;
  const languages =
    about.languages.length === spoken.length &&
    about.languages.every((code) => spoken.includes(code))
      ? null
      : about.languages;
  return {
    name: name && name !== (profile.name ?? "").trim() ? name : null,
    lookingFor:
      section && !same
        ? {
            expected_version: section.version,
            items: items.map((item) => ({
              text: item.text,
              ...(item.scope ? { scope: item.scope } : {}),
            })),
          }
        : null,
    languages,
  };
}
