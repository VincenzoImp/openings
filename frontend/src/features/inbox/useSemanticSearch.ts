import { useQuery } from "@tanstack/react-query";

import { api } from "../../api/client";
import type { JobStatus } from "../../api/types";

export function useSemanticSearch(query: string, statuses: JobStatus[]) {
  return useQuery({
    queryKey: ["semantic", query, statuses],
    queryFn: () => api.semanticSearch(query, { n_results: 50, statuses }),
    enabled: query.trim().length > 1,
    retry: false,
    staleTime: 60_000,
  });
}
