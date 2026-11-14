// The Profile's reads and writes through the generated client: the profile,
// every career entry, every highlight and the entries' files.
import { useQuery } from "@tanstack/react-query";
import { api, call, transfer, type Schema } from "../../api/client";
import { POLL_MS, queryClient } from "../../query/query";
import { shellKeys } from "../../query/shell";

export type Profile = Schema<"Profile">;
export type Entry = Schema<"CareerEntry">;
export type Highlight = Schema<"Highlight">;
export type EntryFile = Schema<"WorkspaceFile">;
export type EntryInput = Schema<"EntryCreate">;
export type ProfileLink = { label: string; url: string };

export const keys = {
  profile: shellKeys.profile,
  entries: ["career", "entries"] as const,
  highlights: ["career", "highlights"] as const,
  files: ["files", "career"] as const,
};

const PAGE = 200;

/** Every page of a list (the API returns at most 200 per page). */
async function everything<Item>(
  read: (offset: number) => Promise<{ items: Item[]; total: number }>,
) {
  const items: Item[] = [];
  for (let offset = 0; ; offset += PAGE) {
    const page = await read(offset);
    items.push(...page.items);
    if (!page.items.length || items.length >= page.total) return items;
  }
}

export function useProfile() {
  return useQuery({
    queryKey: keys.profile,
    queryFn: ({ signal }) =>
      call(api.GET("/api/v1/career/profile", { signal })),
    refetchInterval: POLL_MS,
  });
}

export function useEntries() {
  return useQuery({
    queryKey: keys.entries,
    queryFn: ({ signal }) =>
      everything((offset) =>
        call(
          api.GET("/api/v1/career/entries", {
            params: { query: { summary: false, limit: PAGE, offset } },
            signal,
          }),
        ),
      ),
    refetchInterval: POLL_MS,
  });
}

export function useHighlights() {
  return useQuery({
    queryKey: keys.highlights,
    queryFn: ({ signal }) =>
      everything((offset) =>
        call(
          api.GET("/api/v1/career/highlights", {
            params: { query: { summary: false, limit: PAGE, offset } },
            signal,
          }),
        ),
      ),
    refetchInterval: POLL_MS,
  });
}

export function useEntryFiles() {
  return useQuery({
    queryKey: keys.files,
    queryFn: ({ signal }) =>
      everything((offset) =>
        call(
          api.GET("/api/v1/files", {
            params: {
              query: { owner_type: "career", limit: PAGE, offset },
            },
            signal,
          }),
        ),
      ),
    refetchInterval: POLL_MS,
  });
}

/** The records as the cache has them now (after a refetch, the newest). */
export const cached = {
  profile: () => queryClient.getQueryData<Profile>(keys.profile),
  entries: () => queryClient.getQueryData<Entry[]>(keys.entries) ?? [],
  highlights: () =>
    queryClient.getQueryData<Highlight[]>(keys.highlights) ?? [],
  files: () => queryClient.getQueryData<EntryFile[]>(keys.files) ?? [],
};

export const writes = {
  profile: (body: Schema<"ProfileUpdate">) =>
    call(api.PATCH("/api/v1/career/profile", { body })),
  createEntry: (body: EntryInput) =>
    call(api.POST("/api/v1/career/entries", { body })),
  updateEntry: (id: string, body: Schema<"EntryUpdate">) =>
    call(
      api.PATCH("/api/v1/career/entries/{career_id}", {
        params: { path: { career_id: id } },
        body,
      }),
    ),
  deleteEntry: (id: string, version: number) =>
    call(
      api.DELETE("/api/v1/career/entries/{career_id}", {
        params: {
          path: { career_id: id },
          query: { expected_version: version },
        },
      }),
    ),
  createHighlight: (body: Schema<"HighlightCreate">) =>
    call(api.POST("/api/v1/career/highlights", { body })),
  updateHighlight: (id: string, body: Schema<"HighlightUpdate">) =>
    call(
      api.PATCH("/api/v1/career/highlights/{highlight_id}", {
        params: { path: { highlight_id: id } },
        body,
      }),
    ),
  deleteHighlight: (id: string, version: number) =>
    call(
      api.DELETE("/api/v1/career/highlights/{highlight_id}", {
        params: {
          path: { highlight_id: id },
          query: { expected_version: version },
        },
      }),
    ),
  deleteFile: (id: string, version: number) =>
    call(
      api.DELETE("/api/v1/files/{file_id}", {
        params: { path: { file_id: id }, query: { expected_version: version } },
      }),
    ),
  previewImport: (text: string) =>
    call(
      api.POST("/api/v1/career/import/preview", {
        body: { text, title: "Imported CV" },
      }),
    ),
  import: (body: Schema<"CareerImport">) =>
    call(api.POST("/api/v1/career/import", { body })),
};

async function sha256(file: File) {
  if (!globalThis.crypto?.subtle) return undefined;
  const digest = await crypto.subtle.digest(
    "SHA-256",
    await file.arrayBuffer(),
  );
  return Array.from(new Uint8Array(digest), (n) =>
    n.toString(16).padStart(2, "0"),
  ).join("");
}

/** Attach a file to a career entry: reserve the upload, then send the bytes. */
export async function attachFile(entryId: string, file: File) {
  const grant = await call(
    api.POST("/api/v1/files/uploads", {
      body: {
        owner_type: "career",
        owner_id: entryId,
        name: file.name,
        size: file.size,
        sha256: await sha256(file),
        media_type: /\.pdf$/i.test(file.name)
          ? "application/pdf"
          : file.type || "application/octet-stream",
      },
    }),
  );
  await transfer(grant, file);
}

/** "12 KB", "1.4 MB". */
export function fileSize(bytes: number) {
  if (bytes < 1000) return `${bytes} B`;
  if (bytes < 1_000_000) return `${Math.round(bytes / 1000)} KB`;
  return `${(bytes / 1_000_000).toFixed(1)} MB`;
}

/** The place of an entry, kept in its metadata as `location`. */
export const placeOf = (entry: Pick<Entry, "metadata">) => {
  const value = entry.metadata?.location;
  return typeof value === "string" ? value : "";
};
