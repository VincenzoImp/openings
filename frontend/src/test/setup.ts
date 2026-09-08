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
if (typeof globalThis.localStorage === "undefined") {
  const memory = new Map<string, string>();
  const storage: Storage = {
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
  Object.defineProperty(globalThis, "localStorage", { value: storage, configurable: true });
}

// jsdom has no layout, so virtualized lists would measure a 0px viewport and
// render nothing. Give scroll containers (role="listbox") a fixed size.
for (const [name, value] of [
  ["offsetHeight", 600],
  ["offsetWidth", 900],
] as const) {
  Object.defineProperty(HTMLElement.prototype, name, {
    configurable: true,
    get(this: HTMLElement) {
      return this.getAttribute("role") === "listbox" ? value : 0;
    },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
  window.history.replaceState(null, "", "/");
});
