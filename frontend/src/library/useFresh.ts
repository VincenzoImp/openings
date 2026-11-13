import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import { api } from "../api";
import { useWorkspace } from "../state";

/**
 * Read a record and keep it current: it is read again after any change to
 * one of `scopes` (the first path segment of a REST route, such as "preferences")
 * and after a workspace refresh. Unlike `useResource` the new value always
 * replaces the old one, so the screen must keep its own unsaved text in state.
 */
export function useFresh<T>(path: string | null, initial: T, scopes: string[]) {
  const { revision } = useWorkspace();
  const [data, setData] = useState(initial);
  const [loading, setLoading] = useState(Boolean(path));
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const loaded = useRef<string | null>(null);
  const scope = scopes.join(",");
  useEffect(() => {
    const listener = (event: Event) => {
      const changed = (event as CustomEvent<string>).detail
        .split("?")[0]
        .split("/")
        .filter(Boolean)[0];
      if (scope.split(",").includes(changed)) setTick((n) => n + 1);
    };
    window.addEventListener("openings:changed", listener);
    return () => window.removeEventListener("openings:changed", listener);
  }, [scope]);
  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }
    const abort = new AbortController();
    if (loaded.current !== path) {
      setLoading(true);
      setData(initial);
    }
    setError(null);
    api<T>(path, "GET", undefined, abort.signal)
      .then((value) => {
        if (abort.signal.aborted) return;
        loaded.current = path;
        setData(value);
        setLoading(false);
      })
      .catch((cause) => {
        if (abort.signal.aborted) return;
        setError(
          cause instanceof Error ? cause.message : "Unable to load this view.",
        );
        setLoading(false);
      });
    return () => abort.abort();
  }, [path, revision, tick]);
  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { data, setData, loading, error, reload };
}

/** What `useFresh` returns for a record of type T. */
export interface Fresh<T> {
  data: T;
  setData: Dispatch<SetStateAction<T>>;
  loading: boolean;
  error: string | null;
  reload: () => void;
}
