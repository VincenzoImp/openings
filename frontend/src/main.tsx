import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { queryClient } from "./data/query";
import { WorkspaceProvider } from "./state";
import { applyStoredTheme } from "./shell/theme";
import "./ui/base.css";
import "./design/index.css";

applyStoredTheme();
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <WorkspaceProvider>
        <App />
      </WorkspaceProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
