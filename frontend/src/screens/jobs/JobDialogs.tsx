import { useEffect, useState, type FormEvent } from "react";
import { Check } from "lucide-react";
import { ConflictNotice } from "../../query/ConflictNotice";
import { Button } from "../../ui/Button";
import { Dialog, Drawer } from "../../ui/Dialog";
import { Field, Input, SearchField, Textarea } from "../../ui/Field";
import { formatDay, formatDate } from "../../ui/format";
import { Icon } from "../../ui/Icon";
import { useToast } from "../../ui/Toast";
import { useCorrect, useJobSearch } from "./data";
import { sourceLabel, type Job, type JobSummary } from "./model";

/**
 * Correct a job's role, company, place, address and posting text. A
 * corrected field is kept when its source refreshes the posting. A save
 * that meets a newer version keeps the draft (Reload, Keep editing).
 */
export function CorrectDrawer({
  job,
  onClose,
}: {
  job: Job | null;
  onClose: () => void;
}) {
  const toast = useToast();
  const blank = {
    title: "",
    company: "",
    location: "",
    url: "",
    posting: "",
  };
  const [draft, setDraft] = useState(blank);
  const [version, setVersion] = useState(0);
  const fill = (from: Job) => {
    setDraft({
      title: from.title,
      company: from.company,
      location: from.location,
      url: from.url,
      posting: from.posting,
    });
    setVersion(from.version);
  };
  useEffect(() => {
    if (job) fill(job);
  }, [job]); // A new job to correct starts from what it holds.
  const save = useCorrect(job?.id ?? "");
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!job) return;
    try {
      await save.mutateAsync({
        expected_version: version,
        title: draft.title,
        company: draft.company,
        location: draft.location,
        url: draft.url || undefined,
        posting: draft.posting,
      });
      onClose();
      toast.show({ tone: "success", message: "Details saved" });
    } catch (error) {
      if (!save.conflict && (error as { status?: number }).status !== 409)
        toast.show({
          tone: "error",
          message: `The details were not saved: ${(error as Error).message}`,
        });
    }
  }
  const field =
    (name: keyof typeof blank) => (event: { target: { value: string } }) =>
      setDraft((current) => ({ ...current, [name]: event.target.value }));
  return (
    <Drawer
      open={!!job}
      onClose={onClose}
      title="Correct details"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            type="submit"
            form="jobs-correct"
            kbd="⌘↵"
            disabled={save.isPending}
          >
            Save
          </Button>
        </>
      }
    >
      <form
        id="jobs-correct"
        className="jobs-form"
        onSubmit={submit}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey))
            event.currentTarget.requestSubmit();
        }}
      >
        {save.conflict && (
          <ConflictNotice
            onReload={async () => {
              await save.reload();
              if (job) fill(job);
            }}
            onKeepEditing={async () => {
              await save.keepEditing();
              const current = save.conflict?.currentVersion;
              if (current) setVersion(current);
            }}
          />
        )}
        <Field label="Role" required>
          <Input
            value={draft.title}
            maxLength={400}
            onChange={field("title")}
          />
        </Field>
        <Field label="Company" required>
          <Input
            value={draft.company}
            maxLength={300}
            onChange={field("company")}
          />
        </Field>
        <Field label="Location">
          <Input
            value={draft.location}
            maxLength={500}
            onChange={field("location")}
          />
        </Field>
        <Field label="Address of the posting">
          <Input
            type="url"
            value={draft.url}
            maxLength={4000}
            onChange={field("url")}
          />
        </Field>
        <Field
          label="Posting text"
          hint="Paste the full posting when the source gave only part of it."
        >
          <Textarea
            rows={12}
            value={draft.posting}
            maxLength={200000}
            onChange={field("posting")}
          />
        </Field>
      </form>
    </Drawer>
  );
}

/**
 * Merge a job with another record of the same vacancy, found by its title or
 * company. The other record stays and receives this one's sources, notes,
 * files and applications.
 */
export function MergeDialog({
  job,
  onClose,
  onMerge,
}: {
  job: Job | null;
  onClose: () => void;
  onMerge: (job: Job, target: JobSummary) => void;
}) {
  const [q, setQ] = useState("");
  const [chosen, setChosen] = useState<JobSummary | null>(null);
  useEffect(() => {
    setQ(job?.title ?? "");
    setChosen(null);
  }, [job]);
  const [typed, setTyped] = useState(q);
  useEffect(() => {
    const timer = setTimeout(() => setTyped(q.trim()), 250);
    return () => clearTimeout(timer);
  }, [q]);
  const found = useJobSearch(typed, !!job && typed.length >= 2);
  const options = (found.data ?? []).filter((item) => item.id !== job?.id);
  return (
    <Dialog
      open={!!job}
      onClose={onClose}
      title="Merge with another job"
      description="The job you choose stays and receives this one's sources, notes, files and applications, so you never apply twice."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={!chosen}
            onClick={() => {
              if (job && chosen) onMerge(job, chosen);
            }}
          >
            Merge
          </Button>
        </>
      }
    >
      <SearchField
        label="Find the other job"
        value={q}
        onChange={(event) => {
          setQ(event.target.value);
          setChosen(null);
        }}
      />
      <ul
        className="jobs-filter-list jobs-pick"
        aria-label="Jobs to merge with"
      >
        {options.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              className="ui-menu-item"
              aria-pressed={chosen?.id === item.id}
              onClick={() => setChosen(item)}
            >
              <span className="ui-menu-label jobs-pick-text">
                <span>{item.title}</span>
                <span className="jobs-pick-sub">
                  {[item.company, item.location, formatDay(item.created_at)]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </span>
              {chosen?.id === item.id && <Icon icon={Check} size="sm" />}
            </button>
          </li>
        ))}
        {typed.length >= 2 && found.isFetched && !options.length && (
          <li className="jobs-muted">No other job matches.</li>
        )}
      </ul>
    </Dialog>
  );
}

const KINDS: Record<string, string> = { jobspy: "Search", rss: "Feed" };

/** Where the job was seen: each source, when, and whether it still lists it. */
export function SourcesDialog({
  job,
  onClose,
}: {
  job: Job | null;
  onClose: () => void;
}) {
  const postings = job?.postings ?? [];
  return (
    <Dialog
      open={!!job}
      onClose={onClose}
      title="Sources of this job"
      footer={
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
      }
    >
      {postings.length ? (
        <ul className="jobs-sources">
          {postings.map((posting) => (
            <li key={posting.id}>
              <p className="jobs-sources-name">
                {posting.source_name ||
                  (posting.source_id ? "A removed source" : "Added by address")}
                {posting.source_kind && (
                  <span className="jobs-muted">
                    {" "}
                    · {KINDS[posting.source_kind] || "Company board"}
                  </span>
                )}
              </p>
              <p className="jobs-muted">
                First seen {formatDay(posting.first_seen_at)} · last seen{" "}
                {formatDate(posting.last_seen_at).toLowerCase()}
                {posting.unlisted_at
                  ? ` · no longer listed since ${formatDay(posting.unlisted_at)}`
                  : ""}
              </p>
              {posting.url && (
                <a href={posting.url} target="_blank" rel="noreferrer">
                  {posting.url}
                </a>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="jobs-muted">
          {job && sourceLabel(job) !== "Added by hand"
            ? `${sourceLabel(job)} reported it, but no source of yours has listed it.`
            : "Added by hand: no source has seen it."}
        </p>
      )}
    </Dialog>
  );
}
