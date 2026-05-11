import { render, screen } from "@testing-library/react";

import App from "./App";

test("renders the dashboard shell", () => {
  render(<App />);

  expect(screen.getByRole("heading", { name: "Job Search" })).toBeInTheDocument();
  expect(screen.getByRole("navigation")).toBeInTheDocument();
});
