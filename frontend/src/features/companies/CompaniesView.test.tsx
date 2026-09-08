import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CompaniesView } from "./CompaniesView";
import { facets, job, mockApi, source } from "../../test/mockApi";
import { renderWithProviders } from "../../test/render";

describe("CompaniesView", () => {
  it("lists sources and the postings of a selected company", async () => {
    const { calls } = mockApi([
      {
        path: "/api/sources",
        reply: () => [source(), source({ name: "proton", kind: "greenhouse", enabled: false })],
      },
      { path: "/api/jobs/facets", reply: () => facets() },
      {
        path: "/api/jobs",
        reply: () => ({
          items: [job({ status: "applied" })],
          total: 1,
          limit: 200,
          offset: 0,
        }),
      },
    ]);
    renderWithProviders(<CompaniesView />);
    expect(await screen.findByText("proton")).toBeInTheDocument();
    expect(screen.getByText("disabled")).toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: /Acme/ }));
    expect(await screen.findByTestId("job-row")).toHaveTextContent("Backend Engineer");
    expect(screen.getByText("Applied")).toBeInTheDocument();
    expect(calls.find((call) => call.url.startsWith("/api/jobs?"))?.url).toContain("company=Acme");
  });
});
