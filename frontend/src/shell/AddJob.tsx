import { useEffect, useState, type FormEvent } from "react";
import { useAddJob, useKnownJob } from "../data/shell";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { Field, Input, Textarea } from "../ui/Field";
import { Callout } from "../ui/Page";
import { useToast } from "../ui/Toast";
import { Layers } from "lucide-react";
import { href, navigate } from "./router";

const URL_ONLY = /^https?:\/\/\S+$/;

/** What the one field holds: an address, or the posting's text. */
export function readPasted(value: string) {
  const text = value.trim();
  return URL_ONLY.test(text)
    ? { url: text, posting: "" }
    : { url: "", posting: text };
}

const PLACES: Record<string, string> = {
  new: "in New",
  shortlisted: "shortlisted",
  dismissed: "dismissed",
};

/**
 * The global Add job dialog (sidebar +, the palette, `n`): one field for the
 * posting's address or its text, and optional details. An address already in
 * the workspace is named, so the job can be opened instead of added again.
 */
export function AddJob({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [value, setValue] = useState("");
  const [details, setDetails] = useState({
    title: "",
    company: "",
    location: "",
  });
  const [checked, setChecked] = useState("");
  const add = useAddJob();
  const toast = useToast();
  const pasted = readPasted(value);
  const known = useKnownJob(checked);

  useEffect(() => {
    if (!open) return;
    setValue("");
    setChecked("");
    setDetails({ title: "", company: "", location: "" });
    add.reset();
  }, [open]); // Reset when the dialog opens, not when `add` changes.

  function openJob(id: string) {
    onClose();
    navigate(href("jobs", {}, { job: id }));
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pasted.url && !pasted.posting && !details.title.trim()) return;
    const job = await add
      .mutateAsync({
        ...pasted,
        title: details.title.trim(),
        company: details.company.trim(),
        location: details.location.trim(),
      })
      .catch(() => null);
    if (!job) return;
    toast.show({
      message: `Added “${job.title || "Untitled role"}”`,
      tone: "success",
    });
    openJob(job.id);
  }
  const error = add.error?.message;
  const empty = !value.trim() && !details.title.trim();
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Add a job"
      initialFocus="textarea"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            type="submit"
            form="add-job-form"
            disabled={empty || add.isPending}
          >
            {add.isPending ? "Adding…" : "Add job"}
          </Button>
        </>
      }
    >
      <form
        id="add-job-form"
        className="shell-addjob"
        data-unguarded=""
        onSubmit={submit}
      >
        <Field
          label="Address or posting text"
          hint="Paste the posting's address, or its full text."
          error={error}
        >
          <Textarea
            name="posting"
            rows={3}
            value={value}
            maxLength={200000}
            onChange={(event) => setValue(event.target.value)}
            onBlur={() => setChecked(pasted.url)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.metaKey || event.ctrlKey))
                event.currentTarget.form?.requestSubmit();
            }}
          />
        </Field>
        {known && known.id && (
          <Callout
            icon={Layers}
            title="Already in your workspace"
            actions={
              <Button size="sm" onClick={() => openJob(known.id)}>
                Open it
              </Button>
            }
          >
            {known.title || "Untitled role"}
            {known.company ? ` at ${known.company}` : ""},{" "}
            {PLACES[known.triage] || known.triage}. Adding it again refreshes
            that job.
          </Callout>
        )}
        <details className="shell-disclosure">
          <summary>More details</summary>
          <div className="shell-addjob-details">
            <Field label="Role" optional>
              <Input
                name="title"
                maxLength={400}
                value={details.title}
                onChange={(event) =>
                  setDetails({ ...details, title: event.target.value })
                }
              />
            </Field>
            <Field label="Company" optional>
              <Input
                name="company"
                maxLength={300}
                value={details.company}
                onChange={(event) =>
                  setDetails({ ...details, company: event.target.value })
                }
              />
            </Field>
            <Field label="Location" optional>
              <Input
                name="location"
                maxLength={500}
                value={details.location}
                onChange={(event) =>
                  setDetails({ ...details, location: event.target.value })
                }
              />
            </Field>
          </div>
        </details>
      </form>
    </Dialog>
  );
}
