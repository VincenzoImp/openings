import { queryOptions } from "@tanstack/react-query";

import { listJobs } from "../../api/client";
import type { JobListParams } from "../../api/types";

export const jobsQuery = (params: JobListParams) =>
  queryOptions({
    queryKey: ["jobs", params],
    queryFn: () => listJobs(params),
    staleTime: 30_000
  });
