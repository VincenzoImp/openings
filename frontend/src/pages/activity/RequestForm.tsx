import { useState } from "react";
import {
  api,
  careerEntryLabel,
  type Application,
  type Job,
  type Knowledge,
  type ListResult,
} from "../../api";
import { Button, Field, Loading } from "../../design";
import { useFresh } from "../../library/useFresh";
import { useDebounce } from "../../state";
import type { Act } from "./QuestionItem";

type SubjectType = "job" | "application" | "knowledge";
interface Subject {
  type: SubjectType;
  id: string;
  label: string;
}
const kinds: Record<SubjectType, { label: string; search: string }> = {
  job: { label: "A job", search: "Find the job" },
  application: { label: "An application", search: "Find the application" },
  knowledge: { label: "A Career entry", search: "Find the Career entry" },
};
const jobLabel = (job?: Pick<Job, "title" | "company">) =>
  [job?.title, job?.company].filter(Boolean).join(" · ");
const NONE: ListResult<Job & Application & Knowledge> = { items: [], total: 0 };

/** Search one kind of record and pick the one a request is about. */
function SubjectSearch({
  type,
  onPick,
}: {
  type: SubjectType;
  onPick: (subject: Subject) => void;
}) {
  const [text, setText] = useState("");
  const query = encodeURIComponent(useDebounce(text.trim()));
  const path = {
    job: `/jobs?limit=5&q=${query}`,
    application: `/applications?limit=5&q=${query}`,
    knowledge: `/career/knowledge?summary=true&limit=5&q=${query}`,
  }[type];
  const found = useFresh(path, NONE, []);
  const label = (item: Job & Application & Knowledge) =>
    type === "application"
      ? jobLabel(item.job)
      : type === "job"
        ? jobLabel(item)
        : careerEntryLabel(item);
  return (
    <>
      <Field label={kinds[type].search}>
        <input
          type="search"
          value={text}
          placeholder="Title or company"
          onChange={(event) => setText(event.target.value)}
        />
      </Field>
      {found.loading ? (
        <Loading label="Searching…" />
      ) : found.error ? (
        <p className="caption">{found.error}</p>
      ) : found.data.items.length ? (
        <ul className="list picks" aria-label="Matching records">
          {found.data.items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className="title"
                onClick={() =>
                  onPick({ type, id: item.id, label: label(item) })
                }
              >
                {label(item) || "Untitled"}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="caption">Nothing matches.</p>
      )}
    </>
  );
}

/** Write a request for the agent, about one record or about nothing in particular. */
export function RequestForm({ act, busy }: { act: Act; busy: boolean }) {
  const [text, setText] = useState("");
  const [type, setType] = useState<SubjectType | "">("");
  const [subject, setSubject] = useState<Subject | null>(null);
  const waiting = type !== "" && !subject;
  return (
    <form
      className="body stack"
      onSubmit={async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const outcome = await act(
          () =>
            api("/requests", "POST", {
              text: text.trim(),
              ...(subject
                ? { subject_type: subject.type, subject_id: subject.id }
                : {}),
            }),
          "Request saved. Your agent reads it at its next run.",
        );
        if (outcome !== "ok") return;
        form.dataset.dirty = "false";
        setText("");
        setType("");
        setSubject(null);
      }}
    >
      <Field
        label="What should your agent do?"
        hint="Your agent reads requests at the start of its next run. A request cannot make it submit an application, contact an employer or record Applied."
      >
        <textarea
          rows={3}
          maxLength={4000}
          required
          value={text}
          placeholder="For example: rewrite the letter with more focus on data pipelines."
          onChange={(event) => setText(event.target.value)}
        />
      </Field>
      <Field label="About">
        <select
          value={type}
          onChange={(event) => {
            setType(event.target.value as SubjectType | "");
            setSubject(null);
          }}
        >
          <option value="">Nothing in particular</option>
          {Object.entries(kinds).map(([value, kind]) => (
            <option key={value} value={value}>
              {kind.label}
            </option>
          ))}
        </select>
      </Field>
      {subject ? (
        <p className="spread">
          <span className="grow prose">
            <strong>{subject.label}</strong>
          </span>
          <Button
            type="button"
            variant="quiet"
            size="sm"
            onClick={() => setSubject(null)}
          >
            Change
          </Button>
        </p>
      ) : (
        type && <SubjectSearch key={type} type={type} onPick={setSubject} />
      )}
      <div className="row">
        <Button
          type="submit"
          variant="primary"
          loading={busy}
          disabled={!text.trim() || waiting}
        >
          Send request
        </Button>
        {waiting && (
          <span className="caption">Pick the record, or choose nothing.</span>
        )}
      </div>
    </form>
  );
}
