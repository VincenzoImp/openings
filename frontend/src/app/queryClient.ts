import { QueryClient } from "@tanstack/react-query";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 10_000, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
}
