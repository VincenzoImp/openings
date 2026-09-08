import { useCallback, useState } from "react";
import type { ReactNode } from "react";

import { Button } from "../components/Button";
import { Dialog } from "../components/Dialog";
import { ConfirmContext } from "./confirmContext";
import type { Confirm, ConfirmOptions } from "./confirmContext";

interface Pending extends ConfirmOptions {
  resolve: (value: boolean) => void;
}

/** One confirmation dialog for the whole app: `await confirm({...})`. */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null);

  const confirm = useCallback<Confirm>(
    (options) =>
      new Promise<boolean>((resolve) => {
        setPending({ ...options, resolve });
      }),
    [],
  );

  const close = (value: boolean) => {
    pending?.resolve(value);
    setPending(null);
  };

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Dialog
        open={pending !== null}
        title={pending?.title ?? ""}
        onClose={() => close(false)}
        footer={
          <>
            <Button onClick={() => close(false)}>Cancel</Button>
            <Button
              variant={pending?.danger ? "danger" : "primary"}
              onClick={() => close(true)}
              autoFocus
            >
              {pending?.confirmLabel ?? "Confirm"}
            </Button>
          </>
        }
      >
        <div className="text-sm text-fg-muted">{pending?.message}</div>
      </Dialog>
    </ConfirmContext.Provider>
  );
}
