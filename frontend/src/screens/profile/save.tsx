// Saving a block: one versioned write; on a conflict the draft stays and
// the block shows "Changed elsewhere" (Reload, Keep editing); any other
// failure is said above the fields.
import { useState } from "react";
import { CircleAlert } from "lucide-react";
import { ConflictNotice } from "../../query/ConflictNotice";
import { isConflict, useVersionedMutation } from "../../query/mutation";
import { ApiError } from "../../api/client";
import { Callout } from "../../ui/Page";
import { useToast } from "../../ui/Toast";

/** A failed write, in plain words; nothing without an error. */
export function Failure({
  error,
  title,
}: {
  error: Error | null;
  title: string;
}) {
  if (!error) return null;
  return (
    <div role="alert">
      <Callout icon={CircleAlert} tone="danger" title={title}>
        {error instanceof ApiError && error.fields.length
          ? error.fields.join(" ")
          : error.message}
      </Callout>
    </div>
  );
}

export function useBlockSave<Vars extends object>({
  write,
  saved,
  onReload,
  onKeepEditing,
}: {
  write: (vars: Vars) => Promise<unknown>;
  /** The success toast: past tense, naming the object. */
  saved: (vars: Vars) => string;
  /** Replace the draft with the stored record (read again). */
  onReload: () => void;
  /** Keep the draft, now based on the stored record's version. */
  onKeepEditing: () => void;
}) {
  const toast = useToast();
  // Keep editing reads the record again before the next save may start.
  const [rebasing, setRebasing] = useState(false);
  const mutation = useVersionedMutation<unknown, Vars>({
    touches: ["career", "files"],
    mutationFn: write,
    onReload,
  });
  const notice = mutation.conflict ? (
    <ConflictNotice
      onReload={mutation.reload}
      onKeepEditing={async () => {
        setRebasing(true);
        await mutation.keepEditing();
        onKeepEditing();
        setRebasing(false);
      }}
    />
  ) : (
    <Failure
      error={isConflict(mutation.error) ? null : mutation.error}
      title="Not saved"
    />
  );
  return {
    saving: mutation.isPending || rebasing,
    notice,
    save: async (vars: Vars) => {
      try {
        await mutation.mutateAsync(vars);
        toast.show({ message: saved(vars), tone: "success" });
        return true;
      } catch {
        return false;
      }
    },
  };
}
