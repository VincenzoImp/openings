import { useId, useState } from "react";
import { X } from "lucide-react";

import { Badge } from "../../components/Badge";
import { Input } from "../../components/Field";
import { useJobCommands, useLabels } from "./queries";

export function LabelsEditor({
  jobIds,
  labels,
  autoFocus = false,
}: {
  jobIds: string[];
  labels: string[];
  autoFocus?: boolean;
}) {
  const { addLabels, removeLabels } = useJobCommands();
  const known = useLabels();
  const [draft, setDraft] = useState("");
  const listId = useId();

  const submit = () => {
    const values = draft
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    if (values.length) {
      addLabels.mutate({ jobIds, labels: values });
      setDraft("");
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-1">
      {labels.map((label) => (
        <Badge key={label} tone="accent">
          {label}
          <button
            type="button"
            aria-label={`Remove label ${label}`}
            className="rounded hover:bg-accent/20"
            onClick={() => removeLabels.mutate({ jobIds, labels: [label] })}
          >
            <X size={12} aria-hidden="true" />
          </button>
        </Badge>
      ))}
      <Input
        aria-label="Add label"
        placeholder="Add label…"
        list={listId}
        autoComplete="off"
        spellCheck={false}
        className="!h-7 !w-36 !py-0.5 !text-xs"
        value={draft}
        autoFocus={autoFocus}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            submit();
          }
        }}
      />
      <datalist id={listId}>
        {(known.data ?? [])
          .filter((entry) => !labels.includes(entry.value))
          .map((entry) => (
            <option key={entry.value} value={entry.value} />
          ))}
      </datalist>
    </div>
  );
}
