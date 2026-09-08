import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CompaniesView } from "./CompaniesView";
import { commonRoutes, job, mockApi, source } from "../../test/mockApi";
import { renderWithProviders } from "../../test/render";

describe("CompaniesView", () => {
  it("lists sources with their health and the postings of a selected company", async () => {
    const { calls } = mockApi([
      {
        path: "/api/sources",
        reply: () => [
          source(),
          source({ name: "proton", kind: "greenhouse", enabled: false }),
          source({
            name: "rss",
            kind: "rss",
            last_run: { name: "rss", tasks: 2, succeeded: 1, failed: 1, rows: 3, errors: ["x"] },
          }),
        ],
      },
      { path: "/api/companies/Acme/statuses", reply: () => ({ applied: 1 }) },
      {
        path: "/api/jobs",
        reply: () => ({ items: [job({ status: "applied" })], total: 1, limit: 100, offset: 0 }),
      },
      ...commonRoutes(),
    ]);
    renderWithProviders(<CompaniesView />);
    expect(await screen.findByText("proton")).toBeInTheDocument();
    expect(screen.getByText("disabled")).toBeInTheDocument();
    expect(screen.getByText("partial")).toBeInTheDocument();
    expect(screen.getByText("Pick a company")).toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: /Acme/ }));
    expect(await screen.findByTestId("job-row")).toHaveTextContent("Backend Engineer");
    expect(window.location.search).toContain("company=Acme");
    await waitFor(() => expect(screen.getByText("Applied 1")).toBeInTheDocument());
    expect(calls.find((call) => call.url.startsWith("/api/jobs?"))?.url).toContain("company=Acme");
  });
});
