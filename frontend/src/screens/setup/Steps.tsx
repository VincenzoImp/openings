import { useRef, useState, type FormEvent } from "react";
import {
  ArrowRight,
  Bookmark,
  Bot,
  Check,
  CircleCheck,
  Inbox,
  Send,
} from "lucide-react";
import type { Schema } from "../../api/client";
import { useAddJob } from "../../query/shell";
import { href } from "../../shell/router";
import { Button } from "../../ui/Button";
import { Field, Input, Textarea } from "../../ui/Field";
import { Icon, type LucideIcon } from "../../ui/Icon";
import {
  useExampleTemplate,
  useImport,
  usePreviewImport,
  useSaveAbout,
  useSaveSearch,
  useTestSearch,
  type ImportPreview,
  type Search,
} from "./data";
import { StepFrame } from "./Frame";
import { LANGUAGES, aboutFrom, type About } from "./model";

type Profile = Schema<"Profile">;
type Preferences = Schema<"Preferences">;

const plural = (count: number, one: string, many = `${one}s`) =>
  `${count} ${count === 1 ? one : many}`;

/** A line saying what a step already did. */
function Done({ children }: { children: string }) {
  return (
    <p className="setup-done" role="status">
      <Icon icon={CircleCheck} />
      <span>{children}</span>
    </p>
  );
}

/** Step 1: the name (required), the roles, the place and the languages. */
export function AboutStep({
  profile,
  preferences,
  onNext,
}: {
  profile: Profile;
  preferences: Preferences;
  onNext: () => void;
}) {
  const [about, setAbout] = useState<About>(() =>
    aboutFrom(profile, preferences),
  );
  const [missingName, setMissingName] = useState(false);
  const nameField = useRef<HTMLInputElement>(null);
  const save = useSaveAbout();
  const set = (patch: Partial<About>) => setAbout({ ...about, ...patch });
  const spoken = new Set(about.languages);
  const offered = [
    ...LANGUAGES,
    ...about.languages
      .filter((code) => !LANGUAGES.some(([known]) => known === code))
      .map((code) => [code, code.toUpperCase()] as [string, string]),
  ];

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!about.name.trim()) {
      setMissingName(true);
      nameField.current?.focus();
      return;
    }
    const saved = await save
      .mutateAsync({ about, profile, preferences })
      .then(() => true)
      .catch(() => false);
    if (saved) onNext();
  }
  return (
    <StepFrame
      title="About you"
      lead="What you look for shapes your searches and documents."
      primary={{ label: "Continue", form: "setup-about" }}
      busy={save.isPending}
    >
      <form
        id="setup-about"
        className="setup-form"
        data-unguarded=""
        noValidate
        onSubmit={submit}
      >
        <Field
          label="Your name"
          required
          error={
            missingName && !about.name.trim()
              ? "Add your name to continue."
              : undefined
          }
        >
          <Input
            ref={nameField}
            autoComplete="name"
            value={about.name}
            maxLength={200}
            autoFocus
            onChange={(event) => set({ name: event.target.value })}
          />
        </Field>
        <Field
          label="Roles you're after"
          optional
          hint="For example: data engineer, analytics engineer."
        >
          <Input
            value={about.roles}
            maxLength={300}
            onChange={(event) => set({ roles: event.target.value })}
          />
        </Field>
        <Field label="Where" optional hint="Cities, countries or remote.">
          <Input
            value={about.where}
            maxLength={300}
            onChange={(event) => set({ where: event.target.value })}
          />
        </Field>
        <fieldset className="setup-languages">
          <legend>Languages you speak</legend>
          <div className="setup-chips">
            {offered.map(([code, name]) => (
              <button
                key={code}
                type="button"
                className="setup-chip"
                aria-pressed={spoken.has(code)}
                onClick={() =>
                  set({
                    languages: spoken.has(code)
                      ? about.languages.filter((other) => other !== code)
                      : [...about.languages, code],
                  })
                }
              >
                {spoken.has(code) && <Icon icon={Check} size="sm" />}
                {name}
              </button>
            ))}
          </div>
        </fieldset>
        {save.error && (
          <p className="setup-error" role="alert">
            {save.error.message}
          </p>
        )}
      </form>
    </StepFrame>
  );
}

type Found = { title?: unknown; company?: unknown; location?: unknown };

/** Step 2: a saved search, tested first, or one job by its link. */
export function JobsStep({
  preferences,
  onNext,
  onBack,
}: {
  preferences: Preferences;
  onNext: () => void;
  onBack?: () => void;
}) {
  const start = aboutFrom({}, preferences);
  const [search, setSearch] = useState<Search>({
    query: start.roles,
    location: start.where,
    country: "",
  });
  const [link, setLink] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  const [added, setAdded] = useState<string | null>(null);
  const test = useTestSearch();
  const save = useSaveSearch();
  const add = useAddJob();
  const set = (patch: Partial<Search>) => {
    setSearch({ ...search, ...patch });
    test.reset();
  };
  const preview = test.data;
  const found = (preview?.items ?? []) as Found[];
  const problems = (preview?.diagnostics ?? [])
    .map((item) => String(item.message ?? item.error ?? ""))
    .filter(Boolean);

  async function saveSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const source = await save.mutateAsync(search).catch(() => null);
    if (source) setSaved(source.name);
  }
  async function addJob(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const job = await add
      .mutateAsync({
        url: link.trim(),
        posting: "",
        title: "",
        company: "",
        location: "",
      })
      .catch(() => null);
    if (job) {
      setAdded(job.title || job.url || "the job");
      setLink("");
    }
  }
  const did = Boolean(saved || added);
  return (
    <StepFrame
      title="Find jobs"
      lead="Save a search that runs on its own, or add one job you found."
      primary={{ label: "Continue", onClick: onNext }}
      onBack={onBack}
      onSkip={did ? undefined : onNext}
    >
      <section className="setup-block" aria-labelledby="setup-search">
        <h2 id="setup-search">Add a search</h2>
        {saved ? (
          <Done>{`Saved the search “${saved}”.`}</Done>
        ) : (
          <form className="setup-form" data-unguarded="" onSubmit={saveSearch}>
            <Field label="Keywords">
              <Input
                value={search.query}
                required
                maxLength={300}
                onChange={(event) => set({ query: event.target.value })}
              />
            </Field>
            <div className="setup-pair">
              <Field label="Location" optional>
                <Input
                  value={search.location}
                  maxLength={300}
                  onChange={(event) => set({ location: event.target.value })}
                />
              </Field>
              <Field
                label="Country"
                optional
                hint="The job site's market: switzerland, uk, usa."
              >
                <Input
                  value={search.country}
                  maxLength={100}
                  onChange={(event) => set({ country: event.target.value })}
                />
              </Field>
            </div>
            {preview && (
              <div className="setup-preview" role="status">
                <p>
                  {found.length
                    ? `First results: ${plural(preview.total, "job")}`
                    : "No job found with these words yet."}
                </p>
                {found.length > 0 && (
                  <ul>
                    {found.slice(0, 3).map((job, index) => (
                      <li key={index}>
                        <span>{String(job.title || "Untitled role")}</span>
                        {job.company ? (
                          <span className="setup-muted">
                            {String(job.company)}
                          </span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
                {problems.slice(0, 2).map((problem) => (
                  <p key={problem} className="setup-muted">
                    {problem}
                  </p>
                ))}
              </div>
            )}
            {(test.error || save.error) && (
              <p className="setup-error" role="alert">
                {(test.error || save.error)!.message}
              </p>
            )}
            <div className="setup-actions">
              <Button
                disabled={!search.query.trim() || test.isPending}
                onClick={() => test.mutate(search)}
              >
                {test.isPending ? "Testing…" : "Test"}
              </Button>
              <Button
                type="submit"
                disabled={!search.query.trim() || save.isPending}
              >
                Save search
              </Button>
            </div>
          </form>
        )}
      </section>
      <section className="setup-block" aria-labelledby="setup-link">
        <h2 id="setup-link">Or add one job by its link</h2>
        {added && <Done>{`Added “${added}”.`}</Done>}
        <form className="setup-inline" data-unguarded="" onSubmit={addJob}>
          <Field label="Posting address" error={add.error?.message}>
            <Input
              type="url"
              inputMode="url"
              placeholder="https://"
              value={link}
              onChange={(event) => setLink(event.target.value)}
            />
          </Field>
          <Button
            type="submit"
            disabled={
              !/^https?:\/\/\S+\.\S+/.test(link.trim()) || add.isPending
            }
          >
            Add job
          </Button>
        </form>
      </section>
    </StepFrame>
  );
}

/** Step 3: pasted CV text read into career entries, or the example template. */
export function CvStep({
  onNext,
  onBack,
}: {
  onNext: () => void;
  onBack?: () => void;
}) {
  const [text, setText] = useState("");
  const [imported, setImported] = useState<number | null>(null);
  const read = usePreviewImport();
  const save = useImport();
  const example = useExampleTemplate();
  const preview: ImportPreview | undefined = read.data;
  const entries = (preview?.entries ?? []) as {
    title?: string;
    organization?: string;
  }[];

  async function importIt() {
    if (!preview) return;
    const done = await save.mutateAsync(preview).catch(() => null);
    if (done) {
      setImported(entries.length);
      setText("");
      read.reset();
    }
  }
  const did = imported != null || example.isSuccess;
  return (
    <StepFrame
      title="Your CV"
      lead="Your experience is what every CV and letter is made from."
      primary={{ label: "Continue", onClick: onNext }}
      onBack={onBack}
      onSkip={did ? undefined : onNext}
    >
      <section className="setup-block" aria-labelledby="setup-paste">
        <h2 id="setup-paste">Paste your CV</h2>
        {imported != null && (
          <Done>{`Added ${plural(imported, "entry", "entries")} to your Profile.`}</Done>
        )}
        <form
          className="setup-form"
          data-unguarded=""
          onSubmit={(event) => {
            event.preventDefault();
            read.mutate(text);
          }}
        >
          <Field
            label="CV text"
            hint="Plain text or Markdown; nothing is saved before you add it."
          >
            <Textarea
              rows={7}
              value={text}
              maxLength={500000}
              onChange={(event) => {
                setText(event.target.value);
                read.reset();
              }}
            />
          </Field>
          {preview && (
            <div className="setup-preview" role="status">
              <p>
                {entries.length
                  ? `Found ${plural(entries.length, "entry", "entries")}`
                  : "No entry found in this text."}
              </p>
              {entries.length > 0 && (
                <ul>
                  {entries.slice(0, 5).map((entry, index) => (
                    <li key={index}>
                      <span>{entry.title || "Untitled"}</span>
                      {entry.organization && (
                        <span className="setup-muted">
                          {entry.organization}
                        </span>
                      )}
                    </li>
                  ))}
                  {entries.length > 5 && (
                    <li className="setup-muted">
                      and {entries.length - 5} more
                    </li>
                  )}
                </ul>
              )}
            </div>
          )}
          {(read.error || save.error) && (
            <p className="setup-error" role="alert">
              {(read.error || save.error)!.message}
            </p>
          )}
          <div className="setup-actions">
            {preview && entries.length > 0 ? (
              <Button disabled={save.isPending} onClick={importIt}>
                {`Add ${plural(entries.length, "entry", "entries")}`}
              </Button>
            ) : (
              <Button type="submit" disabled={!text.trim() || read.isPending}>
                {read.isPending ? "Reading…" : "Read it"}
              </Button>
            )}
          </div>
        </form>
      </section>
      <section className="setup-block" aria-labelledby="setup-example">
        <h2 id="setup-example">Or start from the example CV template</h2>
        {example.isSuccess ? (
          <Done>Added the template “Example CV”.</Done>
        ) : (
          <div className="setup-actions">
            <Button
              disabled={example.isPending}
              onClick={() => example.mutate()}
            >
              Use the example template
            </Button>
            {example.error && (
              <p className="setup-error" role="alert">
                {example.error.message}
              </p>
            )}
          </div>
        )}
      </section>
    </StepFrame>
  );
}

const USE: { icon: LucideIcon; text: string }[] = [
  { icon: Inbox, text: "Go through new jobs as they come in." },
  { icon: Bookmark, text: "Shortlist the ones worth applying to." },
  { icon: Send, text: "Apply when an application is Ready." },
];

/** Step 4: how Openings is used, and connecting an agent, optionally. */
export function DoneStep({
  onBack,
  onFinish,
}: {
  onBack?: () => void;
  onFinish: () => void;
}) {
  return (
    <StepFrame
      title="Here's how you'll use Openings"
      primary={{ label: "Go to Today", onClick: onFinish }}
      onBack={onBack}
    >
      <ol className="setup-use">
        {USE.map((line) => (
          <li key={line.text}>
            <span className="setup-use-icon">
              <Icon icon={line.icon} />
            </span>
            {line.text}
          </li>
        ))}
      </ol>
      <aside className="setup-agent" aria-labelledby="setup-agent">
        <Icon icon={Bot} />
        <div>
          <h2 id="setup-agent">
            Connect an AI agent <span className="setup-muted">Optional</span>
          </h2>
          <p>
            Openings has no AI of its own; nothing happens until you ask your
            agent.
          </p>
          <a className="setup-link" href={href("settings")}>
            Set it up in Settings
            <ArrowRight aria-hidden="true" size={14} strokeWidth={1.75} />
          </a>
        </div>
      </aside>
    </StepFrame>
  );
}
