import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// jsdom does not implement scrollIntoView; list views call it when the
// keyboard selection moves.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}

// Web Storage is not guaranteed by the test DOM; the dashboard only needs a
// string map with the Storage interface.
function memoryStorage(): Storage {
  const memory = new Map<string, string>();
  return {
    get length() {
      return memory.size;
    },
    clear: () => memory.clear(),
    getItem: (key) => memory.get(key) ?? null,
    key: (index) => Array.from(memory.keys())[index] ?? null,
    removeItem: (key) => {
      memory.delete(key);
    },
    setItem: (key, value) => {
      memory.set(key, String(value));
    },
  };
}
for (const name of ["localStorage", "sessionStorage"] as const) {
  if (typeof globalThis[name] === "undefined") {
    Object.defineProperty(globalThis, name, { value: memoryStorage(), configurable: true });
  }
}

// Downloads hand a Blob to an object URL; jsdom has no implementation.
if (typeof URL.createObjectURL !== "function") {
  URL.createObjectURL = () => "blob:test";
  URL.revokeObjectURL = () => {};
}

// jsdom has no layout, so virtualized lists would measure a 0px viewport and
// render nothing. Give the virtualized job list a fixed size.
for (const [name, value] of [
  ["offsetHeight", 600],
  ["offsetWidth", 900],
] as const) {
  Object.defineProperty(HTMLElement.prototype, name, {
    configurable: true,
    get(this: HTMLElement) {
      return this.getAttribute("data-testid") === "job-list" ? value : 0;
    },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
  sessionStorage.clear();
  delete document.documentElement.dataset.theme;
  window.history.replaceState(null, "", "/");
});
