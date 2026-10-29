import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, type ListResult } from "./api";
interface Store {
  revision: number;
  refresh: () => void;
  pending: boolean;
  mutate: (
    action: () => Promise<unknown>,
    message?: string,
  ) => Promise<boolean>;
  notify: (message: string, error?: boolean) => void;
  toast: { message: string; error: boolean } | null;
  dismiss: () => void;
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
      const submitted = takeSubmittedForm();
      const wasInert = submitted?.form.inert || false;
      const focused = document.activeElement as HTMLElement | null;
      if (submitted) {
        submitted.form.inert = true;
        submitted.form.setAttribute("aria-busy", "true");
      }
      setPending((n) => n + 1);
      try {
        await action();
        if (
          submitted &&
          submitted.form.dataset.editRevision === submitted.revision
        )
          submitted.form.dataset.dirty = "false";
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
        if (submitted) {
          submitted.form.inert = wasInert;
          submitted.form.removeAttribute("aria-busy");
        }
        setPending((n) => n - 1);
        if (submitted && focused && submitted.form.contains(focused))
          requestAnimationFrame(() => {
            if (focused.isConnected) focused.focus({ preventScroll: true });
          });
      }
    },
    [notify],
  );
  return (
    <Context.Provider
      value={{
        revision,
        refresh,
        pending: pending > 0,
        mutate,
        notify,
        toast,
        dismiss: () => setToast(null),
      }}
    >
      {children}
      <Notification />
    </Context.Provider>
  );
}
export function Notification({ inDialog = false }: { inDialog?: boolean }) {
  const { toast, dismiss } = useWorkspace();
  return toast ? (
    <div
      className={`app-toast ${inDialog ? "dialog-toast" : ""} ${toast.error ? "error" : ""}`}
      role={toast.error ? "alert" : "status"}
    >
      {toast.message}
      <button aria-label="Dismiss notification" onClick={dismiss}>
        ×
      </button>
    </div>
  ) : null;
}
export function useWorkspace() {
  const value = useContext(Context);
  if (!value) throw Error("Missing workspace provider");
  return value;
}
async function readResource<T>(
  path: string,
  signal: AbortSignal,
  allPages: boolean,
): Promise<T> {
  if (!allPages) return api<T>(path, "GET", undefined, signal);
  const [base, search = ""] = path.split("?");
  const params = new URLSearchParams(search);
  params.set("limit", "200");
  params.set("offset", "0");
  const result = await api<ListResult<unknown>>(
    `${base}?${params}`,
    "GET",
    undefined,
    signal,
  );
  let offset = result.items.length;
  while (offset < result.total) {
    params.set("offset", String(offset));
    const page = await api<ListResult<unknown>>(
      `${base}?${params}`,
      "GET",
      undefined,
      signal,
    );
    if (!page.items.length) break;
    result.items.push(...page.items);
    result.total = page.total;
    offset += page.items.length;
  }
  return result as T;
}
export function useResource<T>(
  path: string | null,
  initial: T,
  allPages = false,
) {
  const { revision } = useWorkspace();
  const [changed, setChanged] = useState(0);
  useEffect(() => {
    const listener = (event: Event) => {
      if (path && affected(path, (event as CustomEvent<string>).detail))
        setChanged((n) => n + 1);
    };
    window.addEventListener("openings:changed", listener);
    return () => window.removeEventListener("openings:changed", listener);
  }, [path]);
  const loaded = useRef(false);
  const previousPath = useRef(path);
  const [data, setData] = useState(initial),
    [loading, setLoading] = useState(Boolean(path)),
    [error, setError] = useState<string | null>(null),
    [local, setLocal] = useState(0);
  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }
    if (previousPath.current !== path) {
      previousPath.current = path;
      loaded.current = false;
    }
    const abort = new AbortController();
    if (!loaded.current) setLoading(true);
    setError(null);
    readResource<T>(path, abort.signal, allPages)
      .then((value) => {
        if (!loaded.current || !hasDirtyForms()) setData(value);
        loaded.current = true;
      })
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
  }, [path, revision, local, allPages, changed]);
  return {
    data,
    loading,
    error,
    reload: () => setLocal((n) => n + 1),
    setData,
  };
}

function affected(read: string, changed: string) {
  const scope = (value: string) =>
    value.split("?")[0].split("/").filter(Boolean)[0];
  const a = scope(read),
    b = scope(changed);
  if (a === b) return true;
  if (a === "overview")
    return ["jobs", "applications", "scoring", "sources"].includes(b);
  if (a === "jobs") return ["scoring", "notes"].includes(b);
  if (a === "applications") return ["contexts", "documents"].includes(b);
  if (
    a === "sources" ||
    a === "providers" ||
    a === "collection" ||
    a === "tasks"
  )
    return ["sources", "providers", "collection", "tasks"].includes(b);
  return false;
}
let submittedForm: { form: HTMLFormElement; revision: string } | null = null;
function takeSubmittedForm() {
  const submitted = submittedForm;
  submittedForm = null;
  return submitted;
}
export function hasDirtyForms(scope: ParentNode = document) {
  return !!scope.querySelector("form[data-dirty=true]");
}
export function confirmLeave(scope: ParentNode = document) {
  if (!hasDirtyForms(scope)) return true;
  if (!window.confirm("You have unsaved changes. Leave and discard them?"))
    return false;
  scope
    .querySelectorAll<HTMLFormElement>("form[data-dirty=true]")
    .forEach((form) => {
      form.dataset.dirty = "false";
    });
  return true;
}
export function useFormProtection() {
  useEffect(() => {
    const mark = (event: Event) => {
      const target = event.target as HTMLElement;
      const form = target.closest("form");
      if (form && !form.hasAttribute("data-filter-form")) {
        form.dataset.dirty = "true";
        form.dataset.editRevision = String(
          Number(form.dataset.editRevision || 0) + 1,
        );
      }
    };
    const click = (event: Event) => {
      const target = event.target as HTMLElement;
      if (target.closest("[data-dirty-control]")) mark(event);
      const button = target.closest("button");
      const scope = button?.closest("dialog") || document;
      if (button?.textContent?.trim() === "Cancel" && !confirmLeave(scope)) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    const submit = (event: Event) => {
      const form = event.target as HTMLFormElement;
      const submitted = { form, revision: form.dataset.editRevision || "0" };
      submittedForm = submitted;
      setTimeout(() => {
        if (submittedForm === submitted) submittedForm = null;
      }, 0);
    };
    const finishSubmit = () => {
      const submitted = submittedForm;
      queueMicrotask(() => {
        if (submittedForm === submitted) submittedForm = null;
      });
    };
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (hasDirtyForms()) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    document.addEventListener("input", mark, true);
    document.addEventListener("change", mark, true);
    document.addEventListener("submit", submit, true);
    document.addEventListener("submit", finishSubmit);
    document.addEventListener("click", click, true);
    window.addEventListener("beforeunload", beforeUnload);
    return () => {
      document.removeEventListener("input", mark, true);
      document.removeEventListener("change", mark, true);
      document.removeEventListener("submit", submit, true);
      document.removeEventListener("submit", finishSubmit);
      document.removeEventListener("click", click, true);
      window.removeEventListener("beforeunload", beforeUnload);
    };
  }, []);
}
export function useUrlState(key: string, initial: string) {
  const read = () =>
    (new URLSearchParams(location.hash.split("?")[1] || "").get(key) ??
      initial) as string;
  const [value, setValue] = useState<string>(read);
  useEffect(() => {
    const sync = () => setValue(read());
    window.addEventListener("hashchange", sync);
    window.addEventListener("popstate", sync);
    return () => {
      window.removeEventListener("hashchange", sync);
      window.removeEventListener("popstate", sync);
    };
  }, [key]);
  const update = (next: string) => {
    const [page, query = ""] = location.hash.split("?");
    const params = new URLSearchParams(query);
    if (next === initial || !next) params.delete(key);
    else params.set(key, next);
    history.replaceState(
      null,
      "",
      `${page || "#overview"}${params.size ? "?" + params : ""}`,
    );
    window.dispatchEvent(new Event("openings:url"));
    setValue(next);
  };
  return [value, update] as const;
}
export function useDebounce<T>(value: T, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
export function useUrlFilters(defaults: Record<string, string>) {
  const read = () => {
    const p = new URLSearchParams(location.hash.split("?")[1] || "");
    return Object.fromEntries(
      Object.entries(defaults).map(([key, value]) => [
        key,
        p.get(key) ?? value,
      ]),
    );
  };
  const [values, setValues] = useState<Record<string, string>>(read);
  useEffect(() => {
    const sync = () => setValues(read());
    window.addEventListener("hashchange", sync);
    window.addEventListener("popstate", sync);
    return () => {
      window.removeEventListener("hashchange", sync);
      window.removeEventListener("popstate", sync);
    };
  }, []);
  const update = (patch: Record<string, string>) => {
    const next = { ...values, ...patch };
    const [page, query = ""] = location.hash.split("?");
    const params = new URLSearchParams(query);
    Object.entries(next).forEach(([key, value]) => {
      if (!value || value === defaults[key]) params.delete(key);
      else params.set(key, value);
    });
    history.replaceState(
      null,
      "",
      `${page || "#overview"}${params.size ? "?" + params : ""}`,
    );
    window.dispatchEvent(new Event("openings:url"));
    setValues(next);
  };
  return [values, update] as const;
}
