import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api } from "./api";
interface Store {
  revision: number;
  refresh: () => void;
  pending: boolean;
  mutate: (
    action: () => Promise<unknown>,
    message?: string,
  ) => Promise<boolean>;
  notify: (message: string, error?: boolean) => void;
}
const Context = createContext<Store | null>(null);
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [revision, setRevision] = useState(0),
    [pending, setPending] = useState(0),
    [toast, setToast] = useState<{ message: string; error: boolean } | null>(
      null,
    );
  const refresh = useCallback(() => setRevision((n) => n + 1), []);
  const notify = useCallback(
    (message: string, error = false) => setToast({ message, error }),
    [],
  );
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 6500);
    return () => clearTimeout(timer);
  }, [toast]);
  const mutate = useCallback(
    async (action: () => Promise<unknown>, message = "Saved.") => {
      setPending((n) => n + 1);
      try {
        await action();
        refresh();
        notify(message);
        return true;
      } catch (error) {
        notify(
          error instanceof Error
            ? error.message
            : "The change could not be saved.",
          true,
        );
        return false;
      } finally {
        setPending((n) => n - 1);
      }
    },
    [notify, refresh],
  );
  return (
    <Context.Provider
      value={{ revision, refresh, pending: pending > 0, mutate, notify }}
    >
      {children}
      {toast && (
        <div
          className={`app-toast ${toast.error ? "error" : ""}`}
          role={toast.error ? "alert" : "status"}
        >
          {toast.message}
          <button
            aria-label="Dismiss notification"
            onClick={() => setToast(null)}
          >
            ×
          </button>
        </div>
      )}
    </Context.Provider>
  );
}
export function useWorkspace() {
  const value = useContext(Context);
  if (!value) throw Error("Missing workspace provider");
  return value;
}
export function useResource<T>(path: string | null, initial: T) {
  const { revision } = useWorkspace();
  const [data, setData] = useState(initial),
    [loading, setLoading] = useState(Boolean(path)),
    [error, setError] = useState<string | null>(null),
    [local, setLocal] = useState(0);
  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }
    const abort = new AbortController();
    setLoading(true);
    setError(null);
    api<T>(path, "GET", undefined, abort.signal)
      .then(setData)
      .catch((e) => {
        if (!abort.signal.aborted)
          setError(
            e instanceof Error ? e.message : "Unable to load this view.",
          );
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => abort.abort();
  }, [path, revision, local]);
  return {
    data,
    loading,
    error,
    reload: () => setLocal((n) => n + 1),
    setData,
  };
}
