import { QueryClientProvider } from "@tanstack/react-query";
import type { QueryClient } from "@tanstack/react-query";

import { CompaniesView } from "../features/companies/CompaniesView";
import { InboxView } from "../features/inbox/InboxView";
import { JobView } from "../features/job/JobView";
import { PipelineView } from "../features/pipeline/PipelineView";
import { RunsView } from "../features/runs/RunsView";
import { SystemView } from "../features/system/SystemView";
import { ConfirmProvider } from "./confirm";
import { ErrorBoundary } from "./ErrorBoundary";
import { HotkeyProvider } from "./HotkeyProvider";
import { createQueryClient } from "./queryClient";
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

function Router() {
  const route = useRoute();
  const Current = VIEW_COMPONENTS[route.view];
  const resetKey = route.jobId ? `job:${route.jobId}` : route.view;
  return (
    <Shell view={route.view}>
      <ErrorBoundary resetKey={resetKey}>
        {route.jobId ? <JobView key={route.jobId} jobId={route.jobId} /> : <Current />}
      </ErrorBoundary>
    </Shell>
  );
}

export function App({ queryClient }: { queryClient?: QueryClient }) {
  return (
    <QueryClientProvider client={queryClient ?? createQueryClient()}>
      <ToastProvider>
        <HotkeyProvider>
          <ConfirmProvider>
            <ErrorBoundary>
              <Router />
            </ErrorBoundary>
          </ConfirmProvider>
        </HotkeyProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
