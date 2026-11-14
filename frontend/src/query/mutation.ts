// Writes. A mutation names the resources it changes; on success they are read
// again. A versioned write (a record with `expected_version`) that meets a
// newer version keeps the person's draft and says so: the form shows
// "Changed elsewhere" with Reload and Keep editing (ConflictNotice).
import { useCallback, useState } from "react";
import { useMutation, type UseMutationOptions } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import { invalidate, type Resource } from "./query";

type Options<Data, Vars> = Omit<
  UseMutationOptions<Data, Error, Vars>,
  "mutationFn"
> & {
  mutationFn: (vars: Vars) => Promise<Data>;
  /** The resources this write changes; their queries are read again. */
  touches: readonly Resource[];
};

/** A write through the generated client that refreshes what it changed. */
export function useApiMutation<Data, Vars = void>({
  touches,
  onSettled,
  ...options
}: Options<Data, Vars>) {
  return useMutation<Data, Error, Vars>({
    ...options,
    onSettled: async (...args) => {
      await invalidate(touches);
      await onSettled?.(...args);
    },
  });
}

/** Whether a failure is a version conflict: the record changed elsewhere. */
export const isConflict = (error: unknown): error is ApiError =>
  error instanceof ApiError && error.status === 409;

/**
 * A write of a versioned record (the body carries `expected_version`). The
 * form keeps its own draft in state; this hook never resets it. On a 409:
 *
 * - `conflict` is set, and the form shows ConflictNotice;
 * - `reload()` reads the record again and calls `onReload`, where the form
 *   replaces its draft with the stored record;
 * - `keepEditing()` reads the record again (its new version) and keeps the
 *   draft: the next save is made against the version the person has seen.
 */
export function useVersionedMutation<Data, Vars extends object>({
  onReload,
  ...options
}: Options<Data, Vars> & { onReload?: () => void }) {
  const [conflict, setConflict] = useState<ApiError | null>(null);
  const mutation = useApiMutation<Data, Vars>({
    ...options,
    onMutate: (...args) => {
      setConflict(null);
      return options.onMutate?.(...args);
    },
    onError: (error, ...rest) => {
      if (isConflict(error)) setConflict(error);
      return options.onError?.(error, ...rest);
    },
  });
  const { touches } = options;
  const reload = useCallback(async () => {
    setConflict(null);
    await invalidate(touches);
    onReload?.();
  }, [touches, onReload]);
  const keepEditing = useCallback(async () => {
    setConflict(null);
    await invalidate(touches);
  }, [touches]);
  return { ...mutation, conflict, reload, keepEditing };
}
