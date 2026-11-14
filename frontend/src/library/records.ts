// What screens share about records: the links that open a job or an
// application, and one way to send a change that reports a conflict in words.
import { useState } from "react";
import { ApiError } from "../api";
import { useWorkspace } from "../state";

export type Open = (id: string) => void;
export interface Links {
  onOpenJob: Open;
  onOpenApplication: Open;
}

export type Outcome = "ok" | "conflict" | "error";
/**
 * Send one change. A version conflict reads the records again (`reload`) and
 * says so; whatever the owner typed stays in the open form.
 */
export function useAct(reload: () => void) {
  const { notify } = useWorkspace();
  const [busy, setBusy] = useState(false);
  async function act(
    call: () => Promise<unknown>,
    message: string,
  ): Promise<Outcome> {
    setBusy(true);
    try {
      await call();
      notify(message);
      return "ok";
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        reload();
        notify(
          cause.code === "conflict"
            ? "This changed in another session. The latest version is shown and your text is kept: check it and try again."
            : cause.message,
          true,
        );
        return "conflict";
      }
      notify(
        cause instanceof Error ? cause.message : "The change was not saved.",
        true,
      );
      return "error";
    } finally {
      setBusy(false);
    }
  }
  return { act, busy };
}
