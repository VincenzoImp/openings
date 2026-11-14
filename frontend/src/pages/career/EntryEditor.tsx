import { useState, type FormEvent } from "react";
import {
  api,
  careerEntryLabel,
  knowledgeKinds,
  version,
  type Knowledge,
  type KnowledgeKind,
} from "../../api";
import { Button, EmptyState, ErrorBanner, Field, Loading } from "../../design";
import { Assets } from "../../library/Assets";
import { ConfirmDialog } from "../../library/common";
import { useEditorRecord, useResource, useWorkspace } from "../../state";
import { EntryClaims } from "./Claims";
import { DateFields, SkillsField, dateState, datesOf } from "./fields";

// What the title and the organisation are called for each kind of entry.
const fieldNames: Partial<Record<KnowledgeKind, [string, string]>> = {
  experience: ["Job title", "Organization"],
  education: ["Qualification", "Institution"],
  award: ["Award", "Awarding organization"],
  publication: ["Publication title", "Venue"],
  project: ["Project title", "Organization"],
  course: ["Course title", "Provider"],
  skill: ["Group title", "Organization"],
  language: ["Language or group", "Organization"],
};
/** The detail panel: one entry with its fields, claims and files. */
export function EntryEditor({
  id,
  onSaved,
  onRemoved,
}: {
  /** An entry id, "new", or nothing selected. */
  id: string;
  onSaved: (entry: Knowledge) => void;
  onRemoved: () => void;
}) {
  const resource = useResource<Knowledge | null>(
    id && id !== "new" ? `/career/knowledge/${id}` : null,
    null,
  );
  const loaded = resource.data?.id === id ? resource.data : undefined;
  const record = useEditorRecord(loaded, `/career/knowledge/${id}`);
  if (!id)
    return (
      <section className="card detail" aria-label="Selected entry">
        <EmptyState title="No entry selected">
          Choose an entry to edit it and its claims, or add one.
        </EmptyState>
      </section>
    );
  return (
    <section className="card detail" aria-labelledby="entry-title">
      {resource.error ? (
        <div className="body">
          <ErrorBanner message={resource.error} retry={resource.reload} />
        </div>
      ) : id !== "new" && !record ? (
        <Loading label="Loading the entry…" />
      ) : (
        <EntryForm
          key={record ? `${record.id}-${record.version}` : "new"}
          record={record}
          onSaved={(entry) => {
            resource.setData(entry);
            onSaved(entry);
          }}
          onRemoved={onRemoved}
        />
      )}
    </section>
  );
}

function EntryForm({
  record,
  onSaved,
  onRemoved,
}: {
  record?: Knowledge;
  onSaved: (entry: Knowledge) => void;
  onRemoved: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  const [kind, setKind] = useState<KnowledgeKind>(record?.kind || "experience");
  const [dates, setDates] = useState(() => dateState(record?.dates));
  const [skills, setSkills] = useState(record?.skills || []);
  const [removing, setRemoving] = useState(false);
  const names = fieldNames[kind] || ["Title", "Organization"];
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const position = String(form.get("position") || "");
    const body = {
      kind,
      title: form.get("title"),
      organization: form.get("organization"),
      narrative: form.get("narrative"),
      dates: datesOf(dates),
      skills,
      ...(position ? { position: Number(position) } : {}),
    };
    let saved: Knowledge | undefined;
    const ok = await mutate(async () => {
      saved = await api<Knowledge>(
        record ? `/career/knowledge/${record.id}` : "/career/knowledge",
        record ? "PATCH" : "POST",
        record ? version(record, body) : body,
      );
    }, "Entry saved.");
    if (ok && saved) onSaved(saved);
  }
  return (
    <>
      <header>
        <h2 id="entry-title" className="grow">
          {record ? `Edit entry: ${record.title}` : "New entry"}
        </h2>
        {record && (
          <Button
            size="sm"
            variant="quiet danger"
            disabled={pending}
            onClick={() => setRemoving(true)}
          >
            Delete
          </Button>
        )}
        <Button
          size="sm"
          variant="primary"
          form="entry-form"
          disabled={pending}
        >
          Save entry
        </Button>
      </header>
      <form id="entry-form" className="body form-grid" onSubmit={save}>
        <Field label="Kind">
          <select
            name="kind"
            value={kind}
            onChange={(event) => setKind(event.target.value as KnowledgeKind)}
          >
            {Object.entries(knowledgeKinds).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label={names[0]}>
          <input
            name="title"
            required
            maxLength={300}
            defaultValue={record?.title}
          />
        </Field>
        <Field label={`${names[1]} (optional)`}>
          <input
            name="organization"
            maxLength={300}
            defaultValue={record?.organization}
          />
        </Field>
        <Field
          label="Order"
          hint="Lower numbers come first. Empty adds a new entry at the end."
        >
          <input
            name="position"
            type="number"
            min={0}
            step={1}
            defaultValue={record?.position}
          />
        </Field>
        <DateFields value={dates} onChange={setDates} />
        <SkillsField value={skills} onChange={setSkills} />
        <Field
          label="Description"
          hint="Facts and context. Wording for a CV belongs in claims."
          className="wide"
        >
          <textarea
            name="narrative"
            rows={5}
            defaultValue={record?.narrative}
          />
        </Field>
      </form>
      {record ? (
        <>
          <EntryClaims entry={record} />
          <div className="sub flush">
            <div className="spread">
              <h3>Files</h3>
              <span className="caption">Proof and source material</span>
            </div>
            <Assets
              ownerType="career"
              ownerId={record.id}
              empty="No file yet. Add a certificate, a reference or the source of a fact."
            />
          </div>
        </>
      ) : (
        <p className="sub muted">
          Save the entry first; then add its claims and files.
        </p>
      )}
      {removing && record && (
        <ConfirmDialog
          title="Remove this entry?"
          confirm="Remove entry"
          keep="Keep entry"
          onClose={() => setRemoving(false)}
          onConfirm={async () => {
            if (
              await mutate(
                () =>
                  api(
                    `/career/knowledge/${record.id}?expected_version=${record.version}`,
                    "DELETE",
                  ),
                "Entry removed.",
              )
            ) {
              setRemoving(false);
              onRemoved();
            }
          }}
        >
          <p>
            <strong>{careerEntryLabel(record)}</strong> and its claims and files
            are removed from your record. Applications that were already
            prepared keep the copy they used.
          </p>
        </ConfirmDialog>
      )}
    </>
  );
}
