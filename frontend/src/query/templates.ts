// Templates: the designs CVs and letters are built from, with their files
// (fonts, images, class files, a sample PDF), read and written through the
// generated client. Bytes go through upload grants (files_reserve_upload).
import { useQuery } from "@tanstack/react-query";
import { api, call, download, transfer, type Schema } from "../api/client";
import { useApiMutation, useVersionedMutation } from "./mutation";
import { POLL_MS } from "./query";

export type Template = Schema<"Template">;
export type TemplateKind = "cv" | "letter";
export type TemplateFile = Schema<"WorkspaceFile">;

export const templateKeys = {
  list: ["templates", "list"] as const,
  one: (id: string) => ["templates", "one", id] as const,
  files: (id: string) => ["files", "list", { template: id }] as const,
};

export function useTemplates() {
  return useQuery({
    queryKey: templateKeys.list,
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/templates", {
          params: { query: { summary: true, limit: 200 } },
          signal,
        }),
      ),
    refetchInterval: POLL_MS,
  });
}

export function useTemplate(id: string | null) {
  return useQuery({
    queryKey: templateKeys.one(id ?? ""),
    enabled: !!id,
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/templates/{template_id}", {
          params: { path: { template_id: id! } },
          signal,
        }),
      ),
  });
}

export function useTemplateFiles(id: string | null) {
  return useQuery({
    queryKey: templateKeys.files(id ?? ""),
    enabled: !!id,
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/files", {
          params: {
            query: { owner_type: "template", owner_id: id!, limit: 200 },
          },
          signal,
        }),
      ),
  });
}

export type NewTemplate = Schema<"TemplateCreate">;

export function useCreateTemplate() {
  return useApiMutation({
    touches: ["templates"],
    mutationFn: (body: NewTemplate) =>
      call(api.POST("/api/v1/templates", { body })),
  });
}

export type TemplateChange = Omit<Schema<"TemplateUpdate">, "expected_version">;

/** Edit a template with its version; a conflict keeps the form's draft. */
export function useUpdateTemplate(
  template: Template | undefined,
  onReload?: () => void,
) {
  return useVersionedMutation({
    touches: ["templates"],
    onReload,
    mutationFn: (change: TemplateChange) =>
      call(
        api.PATCH("/api/v1/templates/{template_id}", {
          params: { path: { template_id: template!.id } },
          body: { ...change, expected_version: template!.version },
        }),
      ),
  });
}

export function useDeleteTemplate() {
  return useApiMutation({
    touches: ["templates", "files"],
    drops: (template) => [
      templateKeys.one(template.id),
      templateKeys.files(template.id),
    ],
    mutationFn: (template: Template) =>
      call(
        api.DELETE("/api/v1/templates/{template_id}", {
          params: {
            path: { template_id: template.id },
            query: { expected_version: template.version },
          },
        }),
      ),
  });
}

/** The media type an upload declares: TeX sources whatever the browser says. */
export function mediaTypeOf(file: { name: string; type: string }) {
  if (/\.(tex|ltx|cls|sty)$/i.test(file.name)) return "application/x-tex";
  if (/\.pdf$/i.test(file.name)) return "application/pdf";
  return file.type || "application/octet-stream";
}

async function sha256(file: Blob) {
  if (!globalThis.crypto?.subtle) return undefined;
  const digest = await crypto.subtle.digest(
    "SHA-256",
    await file.arrayBuffer(),
  );
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

/** Upload one file to a template: reserve a grant, then send the bytes. */
export async function uploadTemplateFile(templateId: string, file: File) {
  const grant = await call(
    api.POST("/api/v1/files/uploads", {
      body: {
        owner_type: "template",
        owner_id: templateId,
        name: file.name,
        size: file.size,
        sha256: await sha256(file),
        media_type: mediaTypeOf(file),
      },
    }),
  );
  const response = await transfer(grant, file);
  return (await response.json()) as TemplateFile;
}

export function useUploadFiles(templateId: string) {
  return useApiMutation({
    touches: ["files", "templates"],
    mutationFn: async (files: File[]) => {
      for (const file of files) await uploadTemplateFile(templateId, file);
      return files.length;
    },
  });
}

export function useDeleteFile() {
  return useApiMutation({
    touches: ["files", "templates"],
    mutationFn: (file: TemplateFile) =>
      call(
        api.DELETE("/api/v1/files/{file_id}", {
          params: {
            path: { file_id: file.id },
            query: { expected_version: file.version },
          },
        }),
      ),
  });
}

/** A file's bytes, with the session. */
export const fileBytes = (file: TemplateFile) =>
  download(`/api/v1/files/${encodeURIComponent(file.id)}/content?inline=false`);

/**
 * A copy of a template under a new name, with copies of its files. The
 * copy is never the default.
 */
export function useDuplicateTemplate() {
  return useApiMutation({
    touches: ["templates", "files"],
    mutationFn: async ({
      template,
      name,
    }: {
      template: Template;
      name: string;
    }) => {
      const full = await call(
        api.GET("/api/v1/templates/{template_id}", {
          params: { path: { template_id: template.id } },
        }),
      );
      const copy = await call(
        api.POST("/api/v1/templates", {
          body: {
            name,
            kind: full.kind as TemplateKind,
            tex: full.tex ?? "",
            guidance: full.guidance ?? "",
            rules: full.rules ?? {},
            is_default: false,
          },
        }),
      );
      const files = await call(
        api.GET("/api/v1/files", {
          params: {
            query: {
              owner_type: "template",
              owner_id: template.id,
              limit: 200,
            },
          },
        }),
      );
      for (const file of files.items) {
        const { blob } = await fileBytes(file);
        await uploadTemplateFile(
          copy.id,
          new File([blob], file.name, { type: file.media_type }),
        );
      }
      return copy;
    },
  });
}
