import type { FormEvent } from "react";
import {
  api,
  careerEntryLabel,
  version,
  type Claim,
  type Knowledge,
} from "../../api";
import { Button, Dialog, Field } from "../../design";
import { useEditorRecord, useWorkspace } from "../../state";

type Props = {
  record?: Claim;
  /** The entry the claim belongs to, when it is opened from that entry. */
  entry?: Knowledge;
  /** Every entry, to choose or change the one the claim belongs to. */
  entries?: Knowledge[];
  onClose: () => void;
};

/** Add or edit one claim: wording, entry, approval and the star. */
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
  const { mutate, pending } = useWorkspace();
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    // Order and other details are kept as they are: they are not sent.
    const body = {
      knowledge_id: form.get("knowledge_id"),
      text: form.get("text"),
      approved: form.get("approved") === "on",
      always_include: form.get("always_include") === "on",
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
        <div className="field wide">
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
              name="always_include"
              defaultChecked={record?.always_include}
            />
            <span>Always include in my CV</span>
          </label>
        </div>
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
