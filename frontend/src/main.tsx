import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { WorkspaceProvider } from "./state";
import { applyStoredPreferences } from "./shell/preferences";
import "./design/index.css";

applyStoredPreferences();
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <WorkspaceProvider>
      <App />
    </WorkspaceProvider>
  </React.StrictMode>,
);
