// The first-run guide's writes, each an existing operation: profile_update,
// preferences_update, settings_update, sources_create, jobs_create, the career
// import and templates_create. Tests go through sources_preview and the shared
// provider gate (useSourceTest).
import { api, call, download, type Schema } from "../../api/client";
import { useApiMutation } from "../../query/mutation";
import { capitalize, detectBoard, shortUrl, terms } from "../sources/model";
import { aboutChanges, type About } from "./model";

type Profile = Schema<"Profile">;
type Preferences = Schema<"Preferences">;

/** Step 1: the name, what the person looks for and where, their languages. */
export function useSaveAbout() {
  return useApiMutation({
    touches: ["career", "preferences", "settings", "workspace"],
    mutationFn: async ({
      about,
      profile,
      preferences,
    }: {
      about: About;
      profile: Profile;
      preferences: Preferences;
    }) => {
      const changes = aboutChanges(about, profile, preferences);
      if (changes.name !== null)
        await call(
          api.PATCH("/api/v1/career/profile", {
            body: { expected_version: profile.version, name: changes.name },
          }),
        );
      if (changes.lookingFor)
        await call(
          api.PUT("/api/v1/preferences/{section}", {
            params: { path: { section: "looking_for" } },
            body: changes.lookingFor,
          }),
        );
      if (changes.languages)
        await call(
          api.PATCH("/api/v1/settings", {
            body: {
              expected_version: preferences.settings.version,
              spoken_languages: changes.languages,
            },
          }),
        );
    },
  });
}

export interface Search {
  query: string;
  location: string;
  country: string;
}
export const searchSource = (search: Search) => ({
  kind: "jobspy" as const,
  name: [search.query, search.location].filter(Boolean).join(" in "),
  url: "",
  config: {
    query: search.query,
    location: search.location,
    // Without a country only LinkedIn can be searched (it goes by location).
    ...(search.country
      ? { country: search.country }
      : { providers: ["linkedin" as const] }),
  },
});

/** A company's careers page and the words a title must include. */
export interface Board {
  url: string;
  titles: string;
}
export const boardSource = (board: Board) => {
  const url = board.url.trim();
  const detected = detectBoard(url);
  return {
    kind: "auto" as const,
    name: detected?.board ? capitalize(detected.board) : shortUrl(url),
    url,
    config: {},
    filters: { titles: terms(board.titles) },
  };
};

/** Follow the careers page; its first check starts at once. */
export function useSaveBoard() {
  return useApiMutation({
    touches: ["sources", "collection", "workspace"],
    mutationFn: (board: Board) =>
      call(
        api.POST("/api/v1/sources", {
          body: { ...boardSource(board), enabled: true },
        }),
      ),
  });
}

/** Save the search; its first check starts at once, then it runs on its schedule. */
export function useSaveSearch() {
  return useApiMutation({
    touches: ["sources", "collection", "workspace"],
    mutationFn: (search: Search) =>
      call(
        api.POST("/api/v1/sources", {
          body: { ...searchSource(search), enabled: true },
        }),
      ),
  });
}

export type ImportPreview = Schema<"ImportPreviewResult">;

/** Read pasted CV text into career entries, without saving them. */
export function usePreviewImport() {
  return useApiMutation({
    touches: [],
    mutationFn: (text: string) =>
      call(
        api.POST("/api/v1/career/import/preview", {
          body: { text, title: "My CV" },
        }),
      ),
  });
}

/** Save what the preview found. */
export function useImport() {
  return useApiMutation({
    touches: ["career", "workspace"],
    mutationFn: (preview: ImportPreview) =>
      call(
        api.POST("/api/v1/career/import", {
          body: {
            entries: preview.entries as Schema<"EntryCreate">[],
            profile: preview.profile ?? null,
            expected_profile_version:
              (preview.expected_profile_version as number | undefined) ?? null,
          },
        }),
      ),
  });
}

/** Add the shipped example CV template as the default CV template. */
export function useExampleTemplate() {
  return useApiMutation({
    touches: ["templates", "workspace"],
    mutationFn: async () => {
      const { blob } = await download("/api/v1/examples/cv.tex");
      return call(
        api.POST("/api/v1/templates", {
          body: {
            name: "Example CV",
            kind: "cv",
            tex: await blob.text(),
            guidance: "",
            is_default: true,
          },
        }),
      );
    },
  });
}
