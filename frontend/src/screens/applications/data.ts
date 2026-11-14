// The reads and writes of Applications and the application page, through the
// generated client. Keys start with the resource (src/query/query.ts); a
// write names what it touches and those queries are read again.
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, call, transfer, type Schema } from "../../api/client";
import type { operations } from "../../api/schema";
import { useApiMutation, useVersionedMutation } from "../../query/mutation";
import { POLL_MS, type Resource } from "../../query/query";
import { isoDay } from "../../ui/format";
import { NO_REPLY_DAYS } from "./days";
import { type SortKey, type StageFilter } from "./model";

export type ApplicationRow = Schema<"ApplicationRow">;
export type Application = Schema<"Application">;
export type Revision = Schema<"Document">;
export type Patch = Omit<Schema<"ApplicationPatch">, "expected_version">;

/** The job of an application, as both list rows and records carry it. */
export function jobOf(app: { job: unknown }) {
  const job = (app.job ?? {}) as Record<string, unknown>;
  const text = (key: string) =>
    typeof job[key] === "string" ? (job[key] as string) : "";
  return {
    title: text("title") || "Untitled role",
    company: text("company"),
    location: text("location"),
    url: text("url"),
    source: text("source"),
    posting: text("posting"),
  };
}

/** The writes of an application change these resources' reads. */
export const TOUCHES: Resource[] = [
  "applications",
  "documents",
  "stats",
  "jobs",
  "notes",
];

export interface ListParams {
  stage: StageFilter;
  q: string;
  outcome: string;
  waiting: boolean;
  sort: SortKey;
}
/** Rows read at a time; Show more reads the next ones. */
export const PAGE = 200;
type ListQuery = NonNullable<
  operations["applications_list"]["parameters"]["query"]
>;

/**
 * The first `limit` applications of a stage and search, read again while
 * the list is open. Shortlisted leaves out the Ready ones (the server counts
 * them in Shortlisted).
 */
export function useApplicationList(params: ListParams, limit = PAGE) {
  const query: ListQuery = {
    stage: params.stage === "all" ? undefined : params.stage,
    q: params.q || undefined,
    outcome: (params.outcome || undefined) as ListQuery["outcome"],
    needs: params.waiting ? "reply_overdue" : undefined,
    sort: params.sort === "needs" ? "deadline" : params.sort,
    limit,
  };
  const list = useQuery({
    queryKey: ["applications", "list", query],
    queryFn: ({ signal }) =>
      call(api.GET("/api/v1/applications", { params: { query }, signal })),
    placeholderData: keepPreviousData,
    refetchInterval: POLL_MS,
  });
  const page = list.data;
  let items = page?.items ?? [];
  if (params.stage === "shortlisted") items = items.filter((app) => !app.ready);
  return {
    ...list,
    items,
    total: page?.total ?? 0,
    /** Rows the server has beyond the ones read. */
    more: Math.max(0, (page?.total ?? 0) - (page?.items.length ?? 0)),
    counts: page?.stage_counts ?? {},
    noReplyDays: page?.no_reply?.days ?? NO_REPLY_DAYS,
  };
}

/** The Ready applications in Today's order: the send queue. */
export function useReadyQueue() {
  const query = useQuery({
    queryKey: ["applications", "list", { stage: "ready", sort: "deadline" }],
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/applications", {
          params: { query: { stage: "ready", sort: "deadline", limit: PAGE } },
          signal,
        }),
      ),
    refetchInterval: POLL_MS,
  });
  return {
    ...query,
    queue: query.data?.items ?? [],
    noReplyDays: query.data?.no_reply?.days ?? NO_REPLY_DAYS,
  };
}

/** How many applications were marked applied since the start of today. */
export function useSentToday(enabled: boolean) {
  const today = new Date();
  const since = new Date(
    today.getFullYear(),
    today.getMonth(),
    today.getDate(),
  ).toISOString();
  return useQuery({
    queryKey: ["applications", "count", { applied_since: isoDay(today) }],
    enabled,
    queryFn: async ({ signal }) =>
      (
        await call(
          api.GET("/api/v1/applications", {
            params: { query: { applied_since: since, limit: 1 } },
            signal,
          }),
        )
      ).total,
  });
}

export function useApplication(id: string) {
  return useQuery({
    queryKey: ["applications", "one", id],
    enabled: !!id,
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/applications/{application_id}", {
          params: { path: { application_id: id } },
          signal,
        }),
      ),
    refetchInterval: POLL_MS,
  });
}

export type Period = "90d" | "12m" | "all";
export function useStats(period: Period) {
  return useQuery({
    queryKey: ["stats", period],
    queryFn: ({ signal }) =>
      call(api.GET("/api/v1/stats", { params: { query: { period } }, signal })),
  });
}

/** Every revision of an application, newest first (summaries). */
export function useRevisions(applicationId: string) {
  return useQuery({
    queryKey: ["documents", "list", applicationId],
    enabled: !!applicationId,
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/documents", {
          params: {
            query: { application_id: applicationId, summary: true, limit: 200 },
          },
          signal,
        }),
      ),
  });
}

/** One revision with its files and readable text. */
export function useRevision(id: string | null | undefined) {
  return useQuery({
    queryKey: ["documents", "one", id],
    enabled: !!id,
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/documents/{document_id}", {
          params: { path: { document_id: id! } },
          signal,
        }),
      ),
  });
}

export function useComparison(id: string | null) {
  return useQuery({
    queryKey: ["documents", "comparison", id],
    enabled: !!id,
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/documents/{document_id}/comparison", {
          params: { path: { document_id: id! } },
          signal,
        }),
      ),
  });
}

export function useTimeline(applicationId: string) {
  return useQuery({
    queryKey: ["applications", "timeline", applicationId],
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/applications/{application_id}/timeline", {
          params: {
            path: { application_id: applicationId },
            query: { limit: 200 },
          },
          signal,
        }),
      ),
  });
}

/** One application changed: its stage, a reply, its plan or its requirements. */
export function patchApplication(id: string, version: number, patch: Patch) {
  return call(
    api.PATCH("/api/v1/applications/{application_id}", {
      params: { path: { application_id: id } },
      body: { ...patch, expected_version: version },
    }),
  );
}

export function useUpdateApplication() {
  return useApiMutation({
    touches: TOUCHES,
    mutationFn: ({
      id,
      version,
      patch,
    }: {
      id: string;
      version: number;
      patch: Patch;
    }) => patchApplication(id, version, patch),
  });
}

/** A form's write of one application, which keeps its draft on a conflict. */
export function useVersionedUpdate() {
  return useVersionedMutation({
    touches: TOUCHES,
    mutationFn: ({
      id,
      version,
      patch,
    }: {
      id: string;
      version: number;
      patch: Patch;
    }) => patchApplication(id, version, patch),
  });
}

export function useBulk() {
  return useApiMutation({
    touches: TOUCHES,
    mutationFn: (body: Schema<"ApplicationBulk">) =>
      call(api.POST("/api/v1/applications/bulk", { body })),
  });
}

export function useDeleteApplication() {
  return useApiMutation({
    touches: TOUCHES,
    drops: ({ id }) => [
      ["applications", "one", id],
      ["applications", "timeline", id],
      ["documents", "list", id],
    ],
    mutationFn: ({ id, version }: { id: string; version: number }) =>
      call(
        api.DELETE("/api/v1/applications/{application_id}", {
          params: {
            path: { application_id: id },
            query: { expected_version: version },
          },
        }),
      ),
  });
}

export function useDeleteRevision() {
  return useApiMutation({
    touches: TOUCHES,
    drops: ({ id }) => [
      ["documents", "one", id],
      ["documents", "comparison", id],
    ],
    mutationFn: ({ id, version }: { id: string; version: number }) =>
      call(
        api.DELETE("/api/v1/documents/{document_id}", {
          params: {
            path: { document_id: id },
            query: { expected_version: version },
          },
        }),
      ),
  });
}

/** Write the pinned note of an application: a new one, or its edit. */
export function useSaveNote() {
  return useVersionedMutation({
    touches: ["notes", "applications"],
    mutationFn: async ({
      jobId,
      applicationId,
      note,
      body,
    }: {
      jobId: string;
      applicationId: string;
      note?: { id: string; version: number } | null;
      body: string;
    }) =>
      note
        ? call(
            api.PATCH("/api/v1/notes/{note_id}", {
              params: { path: { note_id: note.id } },
              body: { body, expected_version: note.version },
            }),
          )
        : call(
            api.POST("/api/v1/jobs/{job_id}/notes", {
              params: { path: { job_id: jobId } },
              body: { application_id: applicationId, body, pinned: true },
            }),
          ),
  });
}

async function sha256(file: File) {
  // Only in a secure context; the server then names the hash itself.
  if (!globalThis.crypto?.subtle) return undefined;
  const digest = await crypto.subtle.digest(
    "SHA-256",
    await file.arrayBuffer(),
  );
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}
async function spec(file: File) {
  const digest = await sha256(file);
  return {
    name: file.name,
    size: file.size,
    ...(digest && { sha256: digest }),
  };
}
const mediaType = (file: File) =>
  /\.(tex|ltx)$/i.test(file.name)
    ? "application/x-tex"
    : /\.pdf$/i.test(file.name)
      ? "application/pdf"
      : file.type || "application/octet-stream";

/** Reserve an upload for a revision and send the bytes. */
async function attach(
  documentId: string,
  file: File,
  sourceSha256?: string | null,
): Promise<Schema<"WorkspaceFile">> {
  const grant = await call(
    api.POST("/api/v1/files/uploads", {
      body: {
        owner_type: "document",
        owner_id: documentId,
        name: file.name,
        size: file.size,
        sha256: await sha256(file),
        media_type: mediaType(file),
        ...(sourceSha256 ? { source_sha256: sourceSha256 } : {}),
      },
    }),
  );
  return (await transfer(grant, file)).json();
}

export interface Upload {
  applicationId: string;
  kind: "cv" | "letter";
  pdf: File;
  source?: File | null;
  /** The revision this one replaces. */
  previous?: Pick<Revision, "id" | "complete" | "files"> | null;
}

/**
 * Upload a CV or letter: a new revision with its PDF and an optional .tex
 * source (source first, the PDF names it). An incomplete current revision
 * (no PDF yet) receives its PDF instead of being replaced.
 */
export function useUpload() {
  return useApiMutation({
    touches: TOUCHES,
    mutationFn: async ({
      applicationId,
      kind,
      pdf,
      source,
      previous,
    }: Upload) => {
      if (previous && !previous.complete && !source) {
        const tex = (previous.files ?? []).find((file) =>
          /\.(tex|ltx)$/i.test(file.name),
        );
        return attach(previous.id, pdf, tex?.sha256);
      }
      const sourceSpec = source ? await spec(source) : null;
      const created = await call(
        api.POST("/api/v1/documents", {
          body: {
            application_id: applicationId,
            kind,
            title: kind === "cv" ? "CV" : "Letter",
            note: "",
            previous_id: previous?.id ?? null,
            pdf: await spec(pdf),
            ...(sourceSpec?.sha256 ? { source_file: sourceSpec } : {}),
          },
        }),
      );
      let built: string | undefined;
      if (source) {
        const stored: Schema<"WorkspaceFile"> = created.uploads?.source
          ? await (await transfer(created.uploads.source, source)).json()
          : await attach(created.id, source);
        built = stored.sha256;
      }
      if (created.uploads?.pdf && (!source || sourceSpec?.sha256))
        await transfer(created.uploads.pdf, pdf);
      else await attach(created.id, pdf, built);
      return created;
    },
  });
}
