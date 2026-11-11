import { useState, type FormEvent } from "react";
import {
  api,
  careerEntryLabel,
  claimRoles,
  version,
  type Claim,
  type Json,
  type Knowledge,
} from "../../api";
import { Button, Dialog, Field, KeyValueEditor } from "../../design";
import { useEditorRecord, useWorkspace } from "../../state";

type Props = {
  record?: Claim;
  /** The entry the claim belongs to, when it is opened from that entry. */
  entry?: Knowledge;
  /** Every entry, to choose or change the one the claim belongs to. */
  entries?: Knowledge[];
  onClose: () => void;
};

/** Add or edit one claim: wording, entry, approval, selection and details. */
export function ClaimDialog(props: Props) {
  const record = useEditorRecord(
    props.record,
    props.record ? `/career/claims/${props.record.id}` : "",
  );
  return (
    <ClaimForm key={record?.version || "new"} {...props} record={record} />
  );
}

function ClaimForm({ record, entry, entries, onClose }: Props) {
  const { mutate, pending, notify } = useWorkspace();
  const [details, setDetails] = useState<{
    value: Json;
    problem: string | null;
  }>({ value: record?.metadata || {}, problem: null });
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (details.problem) return notify(details.problem, true);
    const form = new FormData(event.currentTarget);
    const position = String(form.get("position") || "");
    const body = {
      knowledge_id: form.get("knowledge_id"),
      text: form.get("text"),
      approved: form.get("approved") === "on",
      default_in_cv: form.get("default_in_cv") === "on",
      role: form.get("role"),
      group: String(form.get("group") || ""),
      ...(position ? { position: Number(position) } : {}),
      metadata: details.value,
    };
    if (
      await mutate(
        () =>
          api(
            record ? `/career/claims/${record.id}` : "/career/claims",
            record ? "PATCH" : "POST",
            record ? version(record, body) : body,
          ),
        "Claim saved.",
      )
    )
      onClose();
  }
  return (
    <Dialog title={record ? "Edit claim" : "Add a claim"} onClose={onClose}>
      <form className="form-grid" onSubmit={save}>
        {entries ? (
          <Field label="Entry" className="wide">
            <select
              name="knowledge_id"
              required
              defaultValue={record?.knowledge_id || entry?.id}
            >
              {entries.map((item) => (
                <option key={item.id} value={item.id}>
                  {careerEntryLabel(item)}
                </option>
              ))}
            </select>
          </Field>
        ) : (
          entry && (
            <>
              <input type="hidden" name="knowledge_id" value={entry.id} />
              <p className="muted wide">{careerEntryLabel(entry)}</p>
            </>
          )
        )}
        <Field
          label="Claim"
          hint="One fact in the words a CV could use."
          className="wide"
        >
          <textarea
            name="text"
            rows={5}
            required
            maxLength={5000}
            defaultValue={record?.text}
          />
        </Field>
        <Field
          label="Role"
          hint="Core carries the account; bench is kept in reserve."
        >
          <select name="role" defaultValue={record?.role || "supporting"}>
            {Object.entries(claimRoles).map(([role, label]) => (
              <option key={role} value={role}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Group" hint="Optional: claims that belong together.">
          <input
            name="group"
            maxLength={100}
            list="claim-groups"
            defaultValue={record?.group}
          />
        </Field>
        <Field
          label="Order"
          hint="Lower numbers come first. Empty adds at the end."
        >
          <input
            name="position"
            type="number"
            min={0}
            step={1}
            defaultValue={record?.position}
          />
        </Field>
        <div className="field">
          <label className="toggle">
            <input
              type="checkbox"
              name="approved"
              defaultChecked={record?.approved}
            />
            <span>I have checked and approve this claim</span>
          </label>
          <label className="toggle">
            <input
              type="checkbox"
              name="default_in_cv"
              defaultChecked={record?.default_in_cv}
            />
            <span>In the CV by default</span>
          </label>
        </div>
        <fieldset className="field wide">
          <legend>Other details</legend>
          <KeyValueEditor
            label="Other details of the claim as keys and values"
            value={record?.metadata || {}}
            onChange={(value, problem) => setDetails({ value, problem })}
          />
        </fieldset>
        <div className="row wide">
          <Button variant="primary" disabled={pending}>
            Save claim
          </Button>
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
