import { useMemo, useSyncExternalStore } from "react";

export function useMediaQuery(query: string): boolean {
  const subscribe = useMemo(
    () => (callback: () => void) => {
      const media = window.matchMedia?.(query);
      media?.addEventListener("change", callback);
      return () => media?.removeEventListener("change", callback);
    },
    [query],
  );
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia?.(query)?.matches ?? false,
    () => false,
  );
}

/** True on devices with a precise pointer (mouse, trackpad): keyboard hints make sense. */
export function useFinePointer(): boolean {
  return useMediaQuery("(hover: hover) and (pointer: fine)");
}

export function useIsMobile(): boolean {
  return useMediaQuery("(max-width: 767px)");
}
