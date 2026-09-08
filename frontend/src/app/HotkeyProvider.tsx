import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { HotkeyContext, SCOPE_ORDER, isTypingTarget } from "./hotkeys";
import type { HotkeyBinding, HotkeyRegistry, HotkeyScope, ShortcutEntry } from "./hotkeys";

export function HotkeyProvider({ children }: { children: ReactNode }) {
  const scopes = useRef<Map<HotkeyScope, Map<string, HotkeyBinding[]>>>(
    new Map(SCOPE_ORDER.map((scope) => [scope, new Map()])),
  );
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey || event.defaultPrevented) {
        return;
      }
      const typing = isTypingTarget(event.target);
      for (const scope of SCOPE_ORDER) {
        const registered = scopes.current.get(scope);
        if (!registered || registered.size === 0) {
          continue;
        }
        for (const bindings of registered.values()) {
          const binding = bindings.find((entry) => entry.key === event.key);
          if (!binding) {
            continue;
          }
          if (typing && event.key !== "Escape") {
            return;
          }
          event.preventDefault();
          binding.run(event);
          return;
        }
        // A dialog owns the keyboard while open, even for keys it does not bind.
        if (scope === "dialog") {
          return;
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const register = useCallback<HotkeyRegistry["register"]>((scope, id, bindings) => {
    scopes.current.get(scope)?.set(id, bindings);
    setVersion((value) => value + 1);
    return () => {
      scopes.current.get(scope)?.delete(id);
      setVersion((value) => value + 1);
    };
  }, []);

  const list = useCallback<HotkeyRegistry["list"]>(() => {
    const seen = new Set<string>();
    const items: ShortcutEntry[] = [];
    for (const scope of ["global", "view", "dialog"] as HotkeyScope[]) {
      for (const bindings of scopes.current.get(scope)?.values() ?? []) {
        for (const binding of bindings) {
          if (!binding.description) {
            continue;
          }
          const label = binding.label ?? binding.key;
          const key = `${binding.group ?? ""}:${label}`;
          if (seen.has(key)) {
            continue;
          }
          seen.add(key);
          items.push({
            group: binding.group ?? "General",
            label,
            description: binding.description,
          });
        }
      }
    }
    return items;
  }, []);

  const registry = useMemo<HotkeyRegistry>(
    () => ({ register, list, version }),
    [register, list, version],
  );

  return <HotkeyContext.Provider value={registry}>{children}</HotkeyContext.Provider>;
}
