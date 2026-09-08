import { useState } from "react";
import { X } from "lucide-react";

import { Badge } from "../../components/Badge";
import { Input } from "../../components/Field";
import { useJobCommands } from "./queries";

export function LabelsEditor({
  jobId,
  labels,
  autoFocus = false,
}: {
  jobId: string;
  labels: string[];
  autoFocus?: boolean;
}) {
  const { addLabels, removeLabels } = useJobCommands();
  const [draft, setDraft] = useState("");

  const submit = () => {
    const values = draft
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    if (values.length) {
      addLabels.mutate({ jobIds: [jobId], labels: values });
      setDraft("");
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-1">
      {labels.map((label) => (
        <Badge key={label} tone="violet" className="gap-1">
          {label}
          <button
            type="button"
            aria-label={`Remove label ${label}`}
            className="rounded hover:bg-violet-200"
            onClick={() => removeLabels.mutate({ jobIds: [jobId], labels: [label] })}
          >
            <X size={12} />
          </button>
        </Badge>
      ))}
      <Input
        aria-label="Add label"
        placeholder="Add label…"
        className="!w-36 !py-0.5 !text-xs"
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
    </div>
  );
}
