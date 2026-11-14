// The design system gallery (ui.html): every primitive of src/ui with
// synthetic data. A development page, not linked from the dashboard: open
// http://127.0.0.1:5173/ui.html under `npm run dev`.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import Gallery from "./Gallery";
import { applyTheme, readTheme } from "../theme";

applyTheme(readTheme());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Gallery />
  </StrictMode>,
);
