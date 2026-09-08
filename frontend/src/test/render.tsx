/* eslint-disable react-refresh/only-export-components */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";

import { ConfirmProvider } from "../app/confirm";
import { HotkeyProvider } from "../app/HotkeyProvider";
import { ToastProvider } from "../app/toast";

export function testQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
}

export function Providers({ client, children }: { client: QueryClient; children: ReactNode }) {
  return (
    <QueryClientProvider client={client}>
      <ToastProvider>
        <HotkeyProvider>
          <ConfirmProvider>{children}</ConfirmProvider>
        </HotkeyProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}

export function renderWithProviders(ui: ReactNode) {
  const client = testQueryClient();
  return {
    client,
    ...render(<Providers client={client}>{ui}</Providers>),
  };
}
