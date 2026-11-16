import { useRef, useState, type FormEvent } from "react";
import {
  ArrowRight,
  Bookmark,
  Bot,
  CircleCheck,
  Inbox,
  Send,
} from "lucide-react";
import type { Schema } from "../../api/client";
import { useAddJob } from "../../query/shell";
import { href } from "../../shell/router";
import { Button } from "../../ui/Button";
import { Field, Input, Textarea } from "../../ui/Field";
import { plural } from "../../ui/format";
import { Icon, type LucideIcon } from "../../ui/Icon";
import {
  boardSource,
  searchSource,
  useExampleTemplate,
  useImport,
  usePreviewImport,
  useSaveAbout,
  useSaveBoard,
  useSaveSearch,
  type Board,
  type ImportPreview,
  type Search,
} from "./data";
import { CountrySelect } from "../sources/CountrySelect";
import {
  CAREERS_ADVICE,
  capitalize,
  countryIn,
  detectBoard,
  localReason,
  testHeading,
} from "../sources/model";
import { useKindLabels, useSourceTest } from "../sources/queries";
import { StepFrame } from "./Frame";
import { LanguagePicker } from "../preferences/LanguagePicker";
import { KEPT_WHOLE, keptWhole } from "../profile/model";
import { aboutFrom, otherLines, type About } from "./model";

type Profile = Schema<"Profile">;
type Preferences = Schema<"Preferences">;

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
  const others = otherLines(preferences);

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
        {others.length > 0 && (
          <div className="setup-preview">
            Your Preferences already say:
            <ul>
              {others.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          </div>
        )}
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
          <LanguagePicker
            value={about.languages}
            onChange={(languages) => set({ languages })}
          />
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

const isLink = (value: string) => /^https?:\/\/\S+\.\S+/.test(value.trim());

/**
 * What a Test found, in a few lines: its heading, the first titles and what
 * each site answered, in words. After an empty or refused search, it offers a
 * careers page instead.
 */
function TestPreview({
  test,
  onCareers,
}: {
  test: ReturnType<typeof useSourceTest>;
  onCareers?: () => void;
}) {
  const preview = test.result;
  if (test.phase === "idle") return null;
  const found = (preview?.items ?? []) as Found[];
  const diagnostics = preview?.diagnostics ?? [];
  const refused = diagnostics.some(
    (item) => item.state === "deferred" || item.state === "error",
  );
  const reasons = diagnostics
    .map((item) =>
      localReason(String(item.message ?? item.error ?? ""), item.next_run_at),
    )
    .filter(Boolean);
  const empty = !test.pending && !found.length;
  return (
    <div className="setup-preview" role="status" aria-busy={test.pending}>
      <p>
        {testHeading({
          phase: test.phase,
          total: preview?.total ?? 0,
          shown: Math.min(found.length, 3),
          listed: preview?.listed,
          failed: !!test.error && !preview,
          fetched: test.fetched,
          fetching: test.fetching,
        })}
      </p>
      {found.length > 0 && (
        <ul>
          {found.slice(0, 3).map((job, index) => (
            <li key={index}>
              <span>{String(job.title || "Untitled role")}</span>
              {job.company ? (
                <span className="setup-muted">{String(job.company)}</span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {test.error && <p className="setup-error">{test.error}</p>}
      {reasons.slice(0, 2).map((reason) => (
        <p key={reason} className="setup-muted">
          {reason}
        </p>
      ))}
      {onCareers && !test.pending && (empty || refused || test.error) && (
        <p className="setup-advice">
          <span>{CAREERS_ADVICE}</span>
          <Button size="sm" onClick={onCareers}>
            Follow a careers page
          </Button>
        </p>
      )}
    </div>
  );
}

/**
 * Step 2: a company's careers page first (read directly, the reliable
 * source), a search of the job sites second, and one job by its link. Test
 * shows what each finds first. "Save and continue" saves whatever is filled
 * in; with nothing filled in, Continue moves on.
 */
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
  const [board, setBoard] = useState<Board>({ url: "", titles: start.roles });
  const [search, setSearch] = useState<Search>({
    query: start.roles,
    location: start.where,
    country: countryIn(start.where),
  });
  const [link, setLink] = useState("");
  const [followed, setFollowed] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [added, setAdded] = useState<string | null>(null);
  const careersField = useRef<HTMLInputElement>(null);
  const labels = useKindLabels();
  const boardTest = useSourceTest();
  const searchTest = useSourceTest();
  const follow = useSaveBoard();
  const save = useSaveSearch();
  const add = useAddJob();
  const setBoardField = (patch: Partial<Board>) => {
    setBoard({ ...board, ...patch });
    boardTest.reset();
  };
  const set = (patch: Partial<Search>) => {
    setSearch({ ...search, ...patch });
    searchTest.reset();
  };
  const detected = detectBoard(board.url);

  const toFollow = !followed && board.url.trim() !== "";
  const toSave = !saved && search.query.trim() !== "";
  const toAdd = link.trim() !== "";
  const busy = follow.isPending || save.isPending || add.isPending;
  async function saveAndContinue(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if ((toAdd && !isLink(link)) || (toFollow && !isLink(board.url))) return;
    let ok = true;
    if (toFollow) {
      const source = await follow.mutateAsync(board).catch(() => null);
      if (source) setFollowed(source.name);
      else ok = false;
    }
    if (toSave) {
      const source = await save.mutateAsync(search).catch(() => null);
      if (source) setSaved(source.name);
      else ok = false;
    }
    if (toAdd) {
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
      } else ok = false;
    }
    if (ok) onNext();
  }
  const toCareers = () => {
    careersField.current?.scrollIntoView?.({ block: "center" });
    careersField.current?.focus();
  };
  const pending = toFollow || toSave || toAdd;
  return (
    <StepFrame
      title="Find jobs"
      lead="Follow a company's careers page or save a search; both are then checked on their own."
      primary={{
        label: pending ? "Save and continue" : "Continue",
        form: "setup-jobs",
      }}
      busy={busy}
      onBack={onBack}
      onSkip={pending ? onNext : undefined}
    >
      <form
        id="setup-jobs"
        className="setup-jobs"
        data-unguarded=""
        noValidate
        onSubmit={saveAndContinue}
      >
        <section className="setup-block" aria-labelledby="setup-careers">
          <h2 id="setup-careers">Follow a company's careers page</h2>
          {followed ? (
            <Done>{`Following “${followed}”. Checking it now.`}</Done>
          ) : (
            <div className="setup-form">
              <Field
                label="Careers page address"
                optional
                error={
                  follow.error?.message ??
                  (toFollow && board.url.trim().length > 8 && !isLink(board.url)
                    ? "Paste the careers page's address, starting with https://."
                    : undefined)
                }
                hint={
                  detected
                    ? `Detected: ${labels[detected.kind] ?? capitalize(detected.kind)}${detected.board ? ` · ${detected.board}` : ""}`
                    : "Greenhouse, Lever, Ashby, Workable, Personio and other job boards are read directly."
                }
              >
                <Input
                  ref={careersField}
                  type="url"
                  inputMode="url"
                  autoComplete="off"
                  placeholder="https://boards.greenhouse.io/example"
                  value={board.url}
                  onChange={(event) =>
                    setBoardField({ url: event.target.value })
                  }
                />
              </Field>
              <Field
                label="Title must include"
                optional
                hint="Words separated by commas; any one is enough."
              >
                <Input
                  value={board.titles}
                  maxLength={300}
                  onChange={(event) =>
                    setBoardField({ titles: event.target.value })
                  }
                />
              </Field>
              <TestPreview test={boardTest} />
              <div className="setup-actions">
                <Button
                  disabled={!isLink(board.url) || boardTest.pending}
                  onClick={() => void boardTest.run(boardSource(board))}
                >
                  {boardTest.pending ? "Testing…" : "Test"}
                </Button>
              </div>
            </div>
          )}
        </section>
        <section className="setup-block" aria-labelledby="setup-search">
          <h2 id="setup-search">Or search job sites</h2>
          {saved ? (
            <Done>{`Saved the search “${saved}”. Checking it now.`}</Done>
          ) : (
            <div className="setup-form">
              <p className="setup-muted">
                Searches LinkedIn; with a country, also Indeed and Glassdoor.
              </p>
              <Field label="Keywords">
                <Input
                  value={search.query}
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
                  hint="With a country, Indeed and Glassdoor are searched too."
                >
                  <CountrySelect
                    value={search.country}
                    onChange={(country) => set({ country })}
                  />
                </Field>
              </div>
              <TestPreview test={searchTest} onCareers={toCareers} />
              {save.error && (
                <p className="setup-error" role="alert">
                  {save.error.message}
                </p>
              )}
              <div className="setup-actions">
                <Button
                  disabled={!search.query.trim() || searchTest.pending}
                  onClick={() => void searchTest.run(searchSource(search))}
                >
                  {searchTest.pending ? "Testing…" : "Test"}
                </Button>
              </div>
            </div>
          )}
        </section>
        <section className="setup-block" aria-labelledby="setup-link">
          <h2 id="setup-link">Or one job you found</h2>
          {added && <Done>{`Added “${added}”.`}</Done>}
          <Field
            label="Link"
            optional
            error={
              add.error?.message ??
              (toAdd && !isLink(link)
                ? "Paste the job's link, starting with https://."
                : undefined)
            }
          >
            <Input
              type="url"
              inputMode="url"
              placeholder="https://"
              value={link}
              onChange={(event) => setLink(event.target.value)}
            />
          </Field>
        </section>
      </form>
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
  // Text the reader could not split is kept whole, as one entry.
  const whole = !!preview && keptWhole(preview);

  async function importIt() {
    if (!preview) return;
    const done = await save.mutateAsync(preview).catch(() => null);
    if (done) {
      setImported(whole ? 0 : entries.length);
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
          <Done>
            {imported
              ? `Added ${plural(imported, "entry", "entries")} to your Profile.`
              : "Added your CV to your Profile as one entry."}
          </Done>
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
                {whole
                  ? KEPT_WHOLE
                  : entries.length
                    ? `Found ${plural(entries.length, "entry", "entries")}`
                    : "No entry found in this text."}
              </p>
              {entries.length > 0 && !whole && (
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
                {whole
                  ? "Add it to your Profile"
                  : `Add ${plural(entries.length, "entry", "entries")}`}
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
            <Icon icon={ArrowRight} size="sm" />
          </a>
        </div>
      </aside>
    </StepFrame>
  );
}
