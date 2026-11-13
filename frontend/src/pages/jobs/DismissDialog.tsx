import { useState } from "react";
import { Button, Dialog, Field } from "../../design";
import { useWorkspace } from "../../state";

/** Dismiss one or several jobs, with an optional reason shown beside each dismissal. */
export function DismissDialog({
  what,
  onConfirm,
  onClose,
}: {
  /** "Data Engineer" or "3 jobs". */
  what: string;
  onConfirm: (reason: string) => void;
  onClose: () => void;
}) {
  const { pending } = useWorkspace();
  const [reason, setReason] = useState("");
  return (
    <Dialog
      title={`Dismiss ${what}?`}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Keep</Button>
          <Button
            variant="primary"
            disabled={pending}
            onClick={() => onConfirm(reason.trim())}
          >
            Dismiss
          </Button>
        </>
      }
    >
      <div className="stack">
        <p>
          A dismissed job is remembered, so it is not collected again, and it
          can be restored at any time.
        </p>
        <Field label="Why (optional)" hint="Shown beside the dismissal.">
          <input
            value={reason}
            maxLength={500}
            onChange={(event) => setReason(event.target.value)}
          />
        </Field>
      </div>
    </Dialog>
  );
}
