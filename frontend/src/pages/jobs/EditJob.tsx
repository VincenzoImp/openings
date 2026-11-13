import { useState, type FormEvent } from "react";
import { api, type Job } from "../../api";
import { Banner, Button, Field, KeyValueEditor } from "../../design";
import { useWorkspace } from "../../state";

/**
 * Correct a job: role, company, place, address, posting text and its other
 * details as keys and values. A corrected field is kept when the source
 * refreshes the posting.
 */
export function EditJob({ job }: { job: Job }) {
  const { mutate, pending } = useWorkspace();
  const [details, setDetails] = useState<{
    value: Record<string, unknown>;
    problem: string | null;
  }>({ value: job.metadata || {}, problem: null });
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (details.problem) return;
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "");
    await mutate(
      () =>
        api(`/jobs/${job.id}`, "PATCH", {
          expected_version: job.version,
          title: text("title"),
          company: text("company"),
          location: text("location"),
          url: text("url") || undefined,
          posting: text("posting"),
          metadata: details.value,
        }),
      "Job details saved.",
    );
  }
  return (
    <form className="stack" onSubmit={save} aria-label="Correct this job">
      <div className="form-grid">
        <Field label="Role">
          <input
            name="title"
            required
            maxLength={400}
            defaultValue={job.title}
          />
        </Field>
        <Field label="Company">
          <input
            name="company"
            required
            maxLength={300}
            defaultValue={job.company}
          />
        </Field>
        <Field label="Location">
          <input name="location" maxLength={500} defaultValue={job.location} />
        </Field>
        <Field label="Address of the posting">
          <input
            name="url"
            type="url"
            maxLength={4000}
            defaultValue={job.url}
          />
        </Field>
      </div>
      <Field
        label="Posting text"
        hint="Paste the full posting when the source gave only part of it."
      >
        <textarea
          name="posting"
          rows={8}
          maxLength={200000}
          defaultValue={job.posting}
        />
      </Field>
      <fieldset className="stack">
        <legend>Other details</legend>
        <p className="caption">
          What the source reported, such as salary or work style. Collection
          reads some of them; you can correct or add any.
        </p>
        <KeyValueEditor
          label="Other details of this job as keys and values"
          value={job.metadata || {}}
          onChange={(value, problem) => setDetails({ value, problem })}
        />
      </fieldset>
      {details.problem && <Banner tone="danger">{details.problem}</Banner>}
      <div className="row">
        <Button
          variant="primary"
          size="sm"
          disabled={pending || !!details.problem}
        >
          Save the details
        </Button>
      </div>
    </form>
  );
}
