import { useState, type FormEvent } from "react";
import { api, date, type Job } from "../../api";
import { Banner, Button, Dialog, Field } from "../../design";
import { useWorkspace } from "../../state";

interface Resolved {
  items: (Pick<Job, "id" | "title" | "company" | "triage" | "created_at"> & {
    matched_by: string[];
  })[];
}
const PLACES: Record<string, string> = {
  new: "in New",
  shortlisted: "shortlisted",
  dismissed: "dismissed",
};

/**
 * Add a job by its address or pasted text. The address is looked up first,
 * so a job already in the workspace opens instead of being added twice.
 */
export function AddJob({
  onClose,
  onOpenJob,
}: {
  onClose: () => void;
  onOpenJob: (id: string) => void;
}) {
  const { mutate, pending } = useWorkspace();
  const [known, setKnown] = useState<Resolved["items"]>([]);
  async function check(url: string) {
    setKnown([]);
    if (!/^https?:\/\/\S+\.\S+/.test(url)) return;
    try {
      const found = await api<Resolved>(
        `/jobs/resolve?url=${encodeURIComponent(url)}`,
      );
      setKnown(found.items);
    } catch {
      // A failed lookup does not stop adding the job.
    }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "").trim();
    let created: Job | undefined;
    const ok = await mutate(async () => {
      created = await api<Job>("/jobs", "POST", {
        url: text("url"),
        title: text("title"),
        company: text("company"),
        location: text("location"),
        posting: text("posting"),
      });
    }, "Job added.");
    if (ok && created) {
      onOpenJob(created.id);
    }
  }
  return (
    <Dialog title="Add a job" onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <p>
          Give its address, paste the posting, or both. If the page cannot be
          read, you can complete the text later.
        </p>
        <Field label="Address of the posting">
          <input
            name="url"
            type="url"
            placeholder="https://company.example/careers/role"
            onBlur={(event) => void check(event.target.value.trim())}
          />
        </Field>
        {known.length > 0 && (
          <Banner
            tone="info"
            title="Already in your workspace"
            action={
              <Button
                size="sm"
                type="button"
                onClick={() => onOpenJob(known[0].id)}
              >
                Open it
              </Button>
            }
          >
            {known[0].title} at {known[0].company}, found{" "}
            {date(known[0].created_at)},{" "}
            {PLACES[known[0].triage] || known[0].triage}. Adding it again
            refreshes that job.
          </Banner>
        )}
        <div className="form-grid">
          <Field label="Role">
            <input
              name="title"
              maxLength={400}
              placeholder="Backend Engineer"
            />
          </Field>
          <Field label="Company">
            <input name="company" maxLength={300} />
          </Field>
          <Field label="Location">
            <input
              name="location"
              maxLength={500}
              placeholder="City or region"
            />
          </Field>
        </div>
        <Field label="Posting text">
          <textarea
            name="posting"
            rows={6}
            maxLength={200000}
            placeholder="Paste the full posting"
          />
        </Field>
        <div className="row">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={pending}>
            Add the job
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
