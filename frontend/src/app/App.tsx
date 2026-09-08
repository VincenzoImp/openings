import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { CompaniesView } from "../features/companies/CompaniesView";
import { InboxView } from "../features/inbox/InboxView";
import { JobView } from "../features/job/JobView";
import { PipelineView } from "../features/pipeline/PipelineView";
import { RunsView } from "../features/runs/RunsView";
import { SystemView } from "../features/system/SystemView";
import { useRoute } from "./router";
import type { View } from "./router";
import { Shell } from "./Shell";
import { ToastProvider } from "./toast";

const VIEW_COMPONENTS: Record<View, () => React.JSX.Element> = {
  inbox: InboxView,
  pipeline: PipelineView,
  companies: CompaniesView,
  runs: RunsView,
  system: SystemView,
};

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 10_000, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
}

function Router() {
  const route = useRoute();
  const Current = VIEW_COMPONENTS[route.view];
  return (
    <Shell view={route.view}>
      {route.jobId ? <JobView key={route.jobId} jobId={route.jobId} /> : <Current />}
    </Shell>
  );
}

export function App({ queryClient }: { queryClient?: QueryClient }) {
  return (
    <QueryClientProvider client={queryClient ?? createQueryClient()}>
      <ToastProvider>
        <Router />
      </ToastProvider>
    </QueryClientProvider>
  );
}
