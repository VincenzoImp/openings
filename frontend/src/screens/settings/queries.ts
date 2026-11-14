// The reads and writes of the Settings screen, over the generated client.
import { useQuery } from "@tanstack/react-query";
import { api, call, type Schema } from "../../api/client";
import { useApiMutation } from "../../query/mutation";

export const settingsKeys = {
  workspace: ["workspace", "info"] as const,
  tokens: ["tokens", "list"] as const,
  skills: ["skills", "list"] as const,
  backups: ["backups", "list"] as const,
  providers: ["providers", "list"] as const,
};

/** This workspace: version, schema, address, storage and who is asking. */
export function useWorkspaceInfo() {
  return useQuery({
    queryKey: settingsKeys.workspace,
    queryFn: ({ signal }) => call(api.GET("/api/v1/workspace", { signal })),
  });
}

/** Whether this session may use owner-only parts (it always may today). */
export function useIsOwner() {
  const info = useWorkspaceInfo();
  return (info.data?.actor ?? "owner") === "owner";
}

export type TokenRow = Schema<"TokenRow">;

export function useTokens(enabled = true) {
  return useQuery({
    queryKey: settingsKeys.tokens,
    enabled,
    queryFn: async ({ signal }) =>
      (await call(api.GET("/api/v1/tokens", { signal }))).items,
  });
}

export function useCreateToken() {
  return useApiMutation({
    touches: ["tokens"],
    mutationFn: (body: Schema<"TokenInput">) =>
      call(api.POST("/api/v1/tokens", { body })),
  });
}

export function useRevokeToken() {
  return useApiMutation({
    touches: ["tokens"],
    mutationFn: (token_id: string) =>
      call(
        api.DELETE("/api/v1/tokens/{token_id}", {
          params: { path: { token_id } },
        }),
      ),
  });
}

/** What the shipped skills let the owner ask their agent. */
export function useSkills() {
  return useQuery({
    queryKey: settingsKeys.skills,
    staleTime: Infinity,
    queryFn: async ({ signal }) => {
      // Without a name, the read is the list of skills.
      const list = (await call(
        api.GET("/api/v1/skills", { signal }),
      )) as Schema<"SkillList">;
      return list.items;
    },
  });
}

export type KeptBackup = Schema<"KeptBackup">;

/** Scheduled backups and copies kept before upgrades. */
export function useBackups(enabled = true) {
  return useQuery({
    queryKey: settingsKeys.backups,
    enabled,
    queryFn: ({ signal }) => call(api.GET("/api/v1/backups", { signal })),
  });
}

export function useDeleteBackup() {
  return useApiMutation({
    touches: ["backups", "workspace"],
    mutationFn: (name: string) =>
      call(
        api.DELETE("/api/v1/backups/{name}", { params: { path: { name } } }),
      ),
  });
}

export function useChangePassword() {
  return useApiMutation({
    touches: [],
    mutationFn: (body: Schema<"PasswordChange">) =>
      call(api.POST("/api/v1/auth/password", { body })),
  });
}

/** The request gate of every job site. */
export function useProviders(enabled = true) {
  return useQuery({
    queryKey: settingsKeys.providers,
    enabled,
    queryFn: async ({ signal }) =>
      (await call(api.GET("/api/v1/providers", { signal }))).items,
  });
}

export function useUpdateProvider() {
  return useApiMutation({
    touches: ["providers"],
    mutationFn: ({
      id,
      ...body
    }: Omit<Schema<"ProviderUpdate">, "clear_cooldown"> & { id: string }) =>
      call(
        api.PATCH("/api/v1/providers/{provider_id}", {
          params: { path: { provider_id: id } },
          body: { clear_cooldown: false, ...body },
        }),
      ),
  });
}
