import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { setToken } from "../api/client";
import { Button } from "../components/Button";
import { Dialog } from "../components/Dialog";
import { Field, Input } from "../components/Field";

export function TokenDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const client = useQueryClient();
  const [draft, setDraft] = useState("");

  const save = () => {
    setToken(draft);
    setDraft("");
    onClose();
    client.invalidateQueries();
  };

  return (
    <Dialog
      open={open}
      title="API token required"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Later</Button>
          <Button variant="primary" onClick={save} disabled={!draft.trim()}>
            Save token
          </Button>
        </>
      }
    >
      <form
        className="flex flex-col gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (draft.trim()) {
            save();
          }
        }}
      >
        <p className="text-sm text-slate-600">
          This server sets <code>OPENINGS_API_TOKEN</code>. Paste it here; it stays in this browser.
        </p>
        <Field label="Token" htmlFor="token-input">
          <Input
            id="token-input"
            type="password"
            autoComplete="off"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
        </Field>
      </form>
    </Dialog>
  );
}
