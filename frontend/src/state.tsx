import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ApiError, api, copyText, type ListResult } from "./api";
import { createPortal } from "react-dom";
import { Toast } from "./design/Toast";
/** A button inside a toast, such as Undo. */
export interface ToastAction {
  label: string;
  run: () => void;
}
interface ToastState {
  message: string;
  error: boolean;
  action?: ToastAction;
  /** Changes with every notification, so a repeated message restarts its timer. */
  id: number;
}
interface Store {
  revision: number;
  refresh: () => void;
  pending: boolean;
  mutate: (
    action: () => Promise<unknown>,
    message?: string,
  ) => Promise<boolean>;
  notify: (message: string, error?: boolean, action?: ToastAction) => void;
  toast: ToastState | null;
  dismiss: () => void;
}
let toastIds = 0;
const Context = createContext<Store | null>(null);
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [revision, setRevision] = useState(0),
    [conflict, setConflict] = useState<{
      form: HTMLFormElement;
      path: string;
    } | null>(null),
    [pending, setPending] = useState(0),
    [toast, setToast] = useState<ToastState | null>(null);
  const refresh = useCallback(() => setRevision((n) => n + 1), []);
  const notify = useCallback(
    (message: string, error = false, action?: ToastAction) =>
      setToast({ message, error, action, id: ++toastIds }),
    [],
  );
  const dismiss = useCallback(() => setToast(null), []);
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
        if (error instanceof ApiError && error.status === 409) {
          if (submitted && error.path && !/\?/.test(error.path))
            setConflict({ form: submitted.form, path: error.path });
          else {
            // A button action has no draft to keep: reload the affected
            // records so the next attempt uses their current version.
            refresh();
            // Views keep their data while another editor has unsaved edits.
            const dirty = hasDirtyForms();
            notify(
              error.code === "conflict"
                ? `This record changed in another session. ${dirty ? "Save or discard your open edits to load the latest version, then try again." : "The latest version is now shown; check it and try again."}`
                : `${error.message}${dirty ? "" : " The view now shows the latest state."}`,
              true,
            );
            return false;
          }
        }
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
    [notify, refresh],
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
        dismiss,
      }}
    >
      {children}
      <Notification />
      {conflict?.form.isConnected &&
        createPortal(
          <ConflictRecovery
            path={conflict.path}
            form={conflict.form}
            onClose={() => setConflict(null)}
            onReload={(record) => {
              conflict.form.dataset.dirty = "false";
              window.dispatchEvent(
                new CustomEvent("openings:record-reloaded", {
                  detail: { path: conflict.path, record },
                }),
              );
              setConflict(null);
              refresh();
            }}
          />,
          conflict.form,
        )}
    </Context.Provider>
  );
}
function ConflictRecovery({
  path,
  form,
  onClose,
  onReload,
}: {
  path: string;
  form: HTMLFormElement;
  onClose: () => void;
  onReload: (record: Record<string, unknown>) => void;
}) {
  const [latest, setLatest] = useState<Record<string, unknown> | null>(null),
    [error, setError] = useState("");
  const { notify } = useWorkspace();
  const fields = Array.from(form.elements).filter(
    (
      element,
    ): element is HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement =>
      "name" in element &&
      !!element.name &&
      !(
        element instanceof HTMLInputElement &&
        ["password", "file", "hidden"].includes(element.type)
      ),
  );
  const currentValues = latest
    ? {
        ...latest,
        ...((latest.policy as object) || {}),
        ...((latest.config as object) || {}),
      }
    : null;
  const draft = fields
    .map(
      (field) =>
        `${field.labels?.[0]?.textContent?.trim() || field.name}: ${field instanceof HTMLInputElement && field.type === "checkbox" ? field.checked : field.value}`,
    )
    .join("\n\n");
  return (
    <section className="conflict-recovery note" role="alert">
      <h3>This record changed in another session</h3>
      <p>
        Your edits are still here. Review the latest values, then copy your
        draft before reloading the editor. Reloading discards this draft.
      </p>
      {error && <p>{error}</p>}
      {latest && (
        <dl>
          {fields
            .filter((field) => Object.hasOwn(currentValues!, field.name))
            .map((field, i) => (
              <div key={i}>
                <dt>{field.labels?.[0]?.textContent?.trim() || field.name}</dt>
                <dd>
                  {typeof currentValues![field.name] === "object"
                    ? JSON.stringify(currentValues![field.name], null, 2)
                    : String(currentValues![field.name] ?? "Empty")}
                </dd>
              </div>
            ))}
        </dl>
      )}
      <div className="actions">
        <button
          type="button"
          className="btn"
          onClick={async () => {
            try {
              if (path.startsWith("/providers/")) {
                const result =
                  await api<ListResult<Record<string, unknown>>>("/providers");
                const record = result.items.find(
                  (item) => item.id === path.split("/").pop(),
                );
                if (!record)
                  throw Error("This provider is no longer available.");
                setLatest(record);
              } else setLatest(await api(path));
              setError("");
            } catch (e) {
              setError(
                e instanceof Error
                  ? e.message
                  : "Unable to load current values.",
              );
            }
          }}
        >
          Review latest values
        </button>
        <button
          type="button"
          className="btn"
          onClick={async () => {
            try {
              await copyText(draft);
              notify("Draft copied. You can reload and reapply your edits.");
            } catch (e) {
              setError(e instanceof Error ? e.message : "Unable to copy.");
            }
          }}
        >
          Copy my draft
        </button>
        <button
          type="button"
          className="btn"
          disabled={!latest}
          onClick={() => {
            if (latest) onReload(latest);
          }}
        >
          Reload editor and discard draft
        </button>
        <button type="button" className="btn" onClick={onClose}>
          Keep editing
        </button>
      </div>
    </section>
  );
}
export function useEditorRecord<T extends { version?: number }>(
  initial: T | undefined,
  path: string,
) {
  const [replacement, setReplacement] = useState<T>();
  useEffect(() => {
    const reload = (event: Event) => {
      const detail = (event as CustomEvent<{ path: string; record: T }>).detail;
      if (detail.path === path) setReplacement(detail.record);
    };
    window.addEventListener("openings:record-reloaded", reload);
    return () => window.removeEventListener("openings:record-reloaded", reload);
  }, [path]);
  return replacement && (replacement.version ?? 0) >= (initial?.version ?? 0)
    ? replacement
    : initial;
}
export function Notification({ inDialog = false }: { inDialog?: boolean }) {
  const { toast, dismiss } = useWorkspace();
  return toast ? (
    <Toast
      key={toast.id}
      message={toast.message}
      error={toast.error}
      action={toast.action}
      inDialog={inDialog}
      onDismiss={dismiss}
    />
  ) : null;
}
export function useWorkspace() {
  const value = useContext(Context);
  if (!value) throw Error("Missing workspace provider");
  return value;
}
export function selectRecords(
  current: Record<string, number>,
  records: { id: string; version: number }[],
  selected: boolean,
  limit = 200,
) {
  const next = { ...current };
  for (const record of records) {
    if (!selected) delete next[record.id];
    else if (next[record.id] === undefined && Object.keys(next).length < limit)
      next[record.id] = record.version;
  }
  return next;
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
    [refreshing, setRefreshing] = useState(Boolean(path)),
    [error, setError] = useState<string | null>(null),
    [local, setLocal] = useState(0);
  useEffect(() => {
    if (!path) {
      setLoading(false);
      setRefreshing(false);
      return;
    }
    if (previousPath.current !== path) {
      previousPath.current = path;
      loaded.current = false;
      setData(initial);
    }
    const abort = new AbortController();
    setRefreshing(true);
    if (!loaded.current) setLoading(true);
    setError(null);
    readResource<T>(path, abort.signal, allPages)
      .then((value) => {
        if (abort.signal.aborted) return;
        // Keep dirty values with the version they were edited against. Clean
        // editors remount on an accepted record version to replace all fields.
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
        if (!abort.signal.aborted) {
          setLoading(false);
          setRefreshing(false);
        }
      });
    return () => abort.abort();
  }, [path, revision, local, allPages, changed]);
  return {
    data,
    loading: loading || previousPath.current !== path,
    refreshing,
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
  // The change log reflects every write.
  if (a === "events") return true;
  if (a === "stats") return ["jobs", "applications", "sources"].includes(b);
  if (a === "jobs") return ["applications", "career", "notes"].includes(b);
  if (a === "applications")
    return [
      "jobs",
      "documents",
      "files",
      "career",
      "templates",
      "preferences",
      // An application carries its pinned note.
      "notes",
    ].includes(b);
  if (a === "career" || a === "templates") return b === "files";
  if (a === "documents") return b === "files";
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
      `${page || "#today"}${params.size ? "?" + params : ""}`,
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
      `${page || "#today"}${params.size ? "?" + params : ""}`,
    );
    window.dispatchEvent(new Event("openings:url"));
    setValues(next);
  };
  return [values, update] as const;
}
