// A career entry as a CV item (title, organization, dates and place, its
// description, highlights, skills and files) and its form.
import { useRef, useState } from "react";
import { FileText, Trash } from "lucide-react";
import { Tag } from "../../ui/Badge";
import { ConfirmDialog } from "../../ui/Dialog";
import { Field, Input, Select, Textarea } from "../../ui/Field";
import { Icon } from "../../ui/Icon";
import { useToast } from "../../ui/Toast";
import { useApiMutation } from "../../query/mutation";
import { EditBlock, ReadBlock, useEditing } from "./Block";
import {
  attachFile,
  cached,
  fileSize,
  placeOf,
  writes,
  type Entry,
  type EntryFile,
  type Highlight,
} from "./data";
import {
  HighlightList,
  HighlightsEditor,
  draftOf,
  type HighlightDraft,
} from "./Highlights";
import { DatesInput, FilesInput, SkillsInput, type FilesDraft } from "./inputs";
import {
  KINDS,
  dateDraft,
  datesOf,
  formatDates,
  placeNew,
  sectionOf,
  type DateDraft,
  type Kind,
} from "./model";
import { useBlockSave } from "./save";

export interface EntryContext {
  highlights: Highlight[];
  files: EntryFile[];
  /** The entries of its section, in their shown order. */
  section: Entry[];
}

/** Up to three skills, then "+N" that shows them all. */
function Skills({ items }: { items: string[] }) {
  const [all, setAll] = useState(false);
  if (!items.length) return null;
  const shown = all ? items : items.slice(0, 3);
  return (
    <div className="pf-tags">
      {shown.map((skill) => (
        <Tag key={skill}>{skill}</Tag>
      ))}
      {!all && items.length > 3 && (
        <button
          type="button"
          className="ui-tag pf-more-tags"
          aria-label={`Show ${items.length - 3} more skills`}
          onClick={() => setAll(true)}
        >
          +{items.length - 3}
        </button>
      )}
    </div>
  );
}

export function FileChips({ files }: { files: EntryFile[] }) {
  if (!files.length) return null;
  return (
    <ul className="pf-files">
      {files.map((file) => (
        <li key={file.id}>
          <a
            className="pf-file"
            href={`/api/v1/files/${encodeURIComponent(file.id)}/content`}
            target="_blank"
            rel="noreferrer"
          >
            <Icon icon={FileText} size="sm" />
            <span className="pf-file-name">{file.name}</span>
            <span className="pf-file-size">{fileSize(file.size)}</span>
          </a>
        </li>
      ))}
    </ul>
  );
}

export function EntryBlock({
  entry,
  context,
  showKind,
}: {
  entry: Entry;
  context: EntryContext;
  showKind: boolean;
}) {
  const editing = useEditing();
  const toast = useToast();
  const [deleting, setDeleting] = useState(false);
  const remove = useApiMutation({
    touches: ["career", "files"],
    mutationFn: () => writes.deleteEntry(entry.id, entry.version),
    // The block is gone once its entry is: the toast comes from the mutation.
    onSuccess: () =>
      toast.show({ message: `Deleted “${entry.title}”`, tone: "success" }),
    onError: (error) => toast.show({ message: error.message, tone: "error" }),
  });
  if (editing.open === entry.id)
    return (
      <EntryForm entry={entry} context={context} kind={entry.kind as Kind} />
    );
  const place = placeOf(entry);
  const dates = formatDates(entry.dates as never);
  // In Education and Other the kind is named, unless the section says it.
  const kind =
    showKind && entry.kind !== "education" ? KINDS[entry.kind as Kind] : "";
  const sub = [kind, entry.organization, place].filter(Boolean).join(" · ");
  const name = entry.title;
  return (
    <>
      <ReadBlock
        name={name}
        className="pf-entry"
        onEdit={() => editing.request(entry.id)}
        menu={[
          {
            id: "delete",
            label: "Delete permanently…",
            icon: Trash,
            danger: true,
            onSelect: () => setDeleting(true),
          },
        ]}
      >
        <article aria-labelledby={`entry-${entry.id}`}>
          <header className="pf-entry-head">
            <h3 id={`entry-${entry.id}`} className="pf-entry-title">
              {entry.title}
            </h3>
            {dates && <span className="pf-entry-dates">{dates}</span>}
          </header>
          {sub && <p className="pf-entry-sub">{sub}</p>}
          {entry.narrative?.trim() && (
            <div className="pf-prose pf-entry-text">
              {entry.narrative
                .trim()
                .split(/\n{2,}/)
                .map((paragraph, at) => (
                  <p key={at}>{paragraph}</p>
                ))}
            </div>
          )}
          <HighlightList items={context.highlights} />
          <Skills items={entry.skills} />
          <FileChips files={context.files} />
        </article>
      </ReadBlock>
      <ConfirmDialog
        open={deleting}
        title={`Delete “${name}” permanently?`}
        confirm="Delete permanently"
        onClose={() => setDeleting(false)}
        onConfirm={() => remove.mutate()}
      >
        <DeleteSummary context={context} />
      </ConfirmDialog>
    </>
  );
}

function DeleteSummary({ context }: { context: EntryContext }) {
  const lost = [
    ...context.highlights.map((item) => item.text ?? item.text_preview),
    ...context.files.map((file) => file.name),
  ];
  return (
    <>
      {lost.length
        ? "Its highlights and files go with it:"
        : "It has no highlights or files."}
      {lost.length > 0 && (
        <span className="pf-lost">
          {lost.map((text, at) => (
            <span key={at}>• {text}</span>
          ))}
        </span>
      )}{" "}
      Applications already prepared keep the copy they used.
    </>
  );
}

// --- The form ---

interface Draft {
  kind: Kind;
  title: string;
  organization: string;
  dates: DateDraft;
  location: string;
  narrative: string;
  skills: string[];
  highlights: HighlightDraft[];
  files: FilesDraft;
}

function draftFrom(
  entry: Entry | null,
  kind: Kind,
  context: EntryContext,
): Draft {
  return {
    kind: (entry?.kind as Kind) ?? kind,
    title: entry?.title ?? "",
    organization: entry?.organization ?? "",
    dates: dateDraft(entry?.dates as never),
    location: entry ? placeOf(entry) : "",
    narrative: entry?.narrative ?? "",
    skills: entry?.skills ?? [],
    highlights: context.highlights.map(draftOf),
    files: { removed: [], added: [] },
  };
}

const FIELDS = [
  "kind",
  "title",
  "organization",
  "location",
  "narrative",
] as const;
const same = (a: unknown, b: unknown) =>
  JSON.stringify(a) === JSON.stringify(b);

/** How many fields of the entry the draft changes. */
const fieldChanges = (draft: Draft, stored: Draft) =>
  FIELDS.filter((key) => draft[key].trim() !== stored[key].trim()).length +
  +!same(datesOf(draft.dates), datesOf(stored.dates)) +
  +!same(draft.skills, stored.skills);

/** And its highlights (added, changed, moved or removed) and files. */
function countChanges(draft: Draft, stored: Draft) {
  const keys = draft.highlights.map((item) => item.key);
  const removed = stored.highlights.filter((item) => !keys.includes(item.key));
  const changed = draft.highlights.filter(
    (item, index) =>
      !same(item, stored.highlights[index]) && (item.id || item.text.trim()),
  );
  return (
    fieldChanges(draft, stored) +
    removed.length +
    changed.length +
    draft.files.removed.length +
    draft.files.added.length
  );
}

export function EntryForm({
  entry,
  context,
  kind,
}: {
  entry: Entry | null;
  context: EntryContext;
  kind: Kind;
}) {
  const [stored] = useState(() => draftFrom(entry, kind, context));
  const [draft, setDraft] = useState(stored);
  const [checked, setChecked] = useState(false);
  // The versions the draft is based on; a write moves them forward.
  const base = useRef({
    entry: entry?.version ?? 0,
    id: entry?.id ?? "",
    highlights: new Map(
      context.highlights.map((item) => [item.id, item.version]),
    ),
    stored: context.highlights,
  });
  const rebase = (replaceDraft: boolean) => {
    const id = base.current.id;
    if (!id) return;
    const fresh = cached.entries().find((item) => item.id === id);
    const highlights = cached
      .highlights()
      .filter((item) => item.career_id === id);
    if (fresh) base.current.entry = fresh.version;
    base.current.highlights = new Map(
      highlights.map((item) => [item.id, item.version]),
    );
    base.current.stored = highlights;
    if (replaceDraft && fresh)
      setDraft(
        draftFrom(fresh, kind, {
          ...context,
          highlights,
          files: cached.files().filter((file) => file.owner_id === id),
        }),
      );
  };
  const changes = countChanges(draft, stored);
  const dates = datesOf(draft.dates);
  const titleError = draft.title.trim() ? undefined : "Add a title.";
  const isNew = !entry;

  const block = useBlockSave({
    write: (value: Draft) => write(value),
    saved: (value) =>
      isNew ? `Added “${value.title.trim()}”` : `Saved “${value.title.trim()}”`,
    onReload: () => rebase(true),
    onKeepEditing: () => rebase(false),
  });

  async function write(value: Draft) {
    const result = datesOf(value.dates);
    if (result.error !== undefined) throw Error(result.error);
    const metadata = { ...(entry?.metadata ?? {}) } as Record<string, unknown>;
    if (value.location.trim()) metadata.location = value.location.trim();
    else delete metadata.location;
    const fields = {
      kind: value.kind,
      title: value.title.trim(),
      organization: value.organization.trim(),
      narrative: value.narrative.trim(),
      skills: value.skills,
      dates: result.dates && {
        ...result.dates,
        current: Boolean(result.dates.current),
      },
      metadata,
    };
    let id = base.current.id;
    if (!id) {
      // A new entry goes where its dates put it in its section.
      const section = cached
        .entries()
        .filter((item) => sectionOf(item.kind) === sectionOf(value.kind))
        .sort((a, b) => a.position - b.position);
      const { position, moves } = placeNew(section, result.dates);
      for (const move of moves) {
        const item = section.find((other) => other.id === move.id)!;
        await writes.updateEntry(item.id, {
          expected_version: item.version,
          position: move.position,
        });
      }
      const created = await writes.createEntry({ ...fields, position });
      id = created.id;
      base.current = { ...base.current, id, entry: created.version };
    } else if (fieldChanges(value, stored)) {
      // Only what the person changed, so a change made elsewhere stays.
      const changed = {
        kind: value.kind !== stored.kind,
        title: value.title.trim() !== stored.title.trim(),
        organization: value.organization.trim() !== stored.organization.trim(),
        narrative: value.narrative.trim() !== stored.narrative.trim(),
        skills: !same(value.skills, stored.skills),
        dates: !same(datesOf(value.dates), datesOf(stored.dates)),
        metadata: value.location.trim() !== stored.location.trim(),
      };
      const saved = await writes.updateEntry(id, {
        ...Object.fromEntries(
          Object.entries(fields).filter(
            ([key]) => changed[key as keyof typeof changed],
          ),
        ),
        expected_version: base.current.entry,
      });
      base.current.entry = saved.version;
    }
    // Highlights: removed, then each in its order.
    for (const old of base.current.stored)
      if (!value.highlights.some((item) => item.id === old.id)) {
        await writes.deleteHighlight(
          old.id,
          base.current.highlights.get(old.id)!,
        );
        base.current.highlights.delete(old.id);
        base.current.stored = base.current.stored.filter(
          (item) => item.id !== old.id,
        );
      }
    const kept = value.highlights.filter((item) => item.text.trim());
    for (const [position, item] of kept.entries()) {
      const old = base.current.stored.find((row) => row.id === item.id);
      if (!item.id || !old) {
        const created = await writes.createHighlight({
          career_id: id,
          text: item.text.trim(),
          approved: item.approved,
          always_include: item.always,
          position,
        });
        // A retry after a conflict must not add it twice.
        setDraft((current) => ({
          ...current,
          highlights: current.highlights.map((row) =>
            row.key === item.key ? { ...row, id: created.id } : row,
          ),
        }));
        item.id = created.id;
        base.current.highlights.set(created.id, created.version);
        base.current.stored = [...base.current.stored, created];
      } else if (
        (old.text ?? "") !== item.text.trim() ||
        old.approved !== item.approved ||
        old.always_include !== item.always ||
        old.position !== position
      ) {
        const saved = await writes.updateHighlight(item.id, {
          expected_version: base.current.highlights.get(item.id)!,
          text: item.text.trim(),
          approved: item.approved,
          always_include: item.always,
          position,
        });
        base.current.highlights.set(saved.id, saved.version);
        base.current.stored = base.current.stored.map((row) =>
          row.id === saved.id ? saved : row,
        );
      }
    }
    for (const fileId of value.files.removed) {
      const file = context.files.find((item) => item.id === fileId);
      if (file) await writes.deleteFile(file.id, file.version);
    }
    for (const file of value.files.added) await attachFile(id, file);
  }

  const set =
    (key: "title" | "organization" | "location" | "narrative") =>
    (event: { target: { value: string } }) =>
      setDraft((value) => ({ ...value, [key]: event.target.value }));
  const label = KINDS[draft.kind].toLowerCase();
  return (
    <EditBlock
      title={isNew ? `New ${label}` : `Edit ${entry.title}`}
      changes={isNew ? Math.max(changes, draft.title.trim() ? 1 : 0) : changes}
      saving={block.saving}
      notice={block.notice}
      className="pf-entry-form"
      onSave={async () => {
        setChecked(true);
        if (titleError || dates.error !== undefined) {
          document
            .querySelector<HTMLElement>(
              titleError ? ".pf-entry-form [name=title]" : ".pf-dates input",
            )
            ?.focus();
          return false;
        }
        return block.save(draft);
      }}
    >
      <div className="pf-fields">
        <Field label="Kind">
          <Select
            name="kind"
            value={draft.kind}
            onChange={(event) =>
              setDraft((value) => ({
                ...value,
                kind: event.target.value as Kind,
              }))
            }
          >
            {Object.entries(KINDS).map(([value, name]) => (
              <option key={value} value={value}>
                {name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Title" error={checked ? titleError : undefined}>
          <Input
            name="title"
            data-autofocus=""
            value={draft.title}
            maxLength={300}
            onChange={set("title")}
            onBlur={() => setChecked(true)}
          />
        </Field>
        <Field label="Organization" optional className="pf-field-wide">
          <Input
            name="organization"
            value={draft.organization}
            maxLength={300}
            onChange={set("organization")}
          />
        </Field>
      </div>
      <DatesInput
        value={draft.dates}
        error={checked && dates.error !== undefined ? dates.error : undefined}
        onChange={(value) =>
          setDraft((current) => ({ ...current, dates: value }))
        }
      />
      <Field label="Location" optional className="pf-field-half">
        <Input
          name="location"
          value={draft.location}
          maxLength={300}
          onChange={set("location")}
        />
      </Field>
      <Field label="Description" optional>
        <Textarea
          name="narrative"
          rows={4}
          value={draft.narrative}
          onChange={set("narrative")}
        />
      </Field>
      <SkillsInput
        value={draft.skills}
        onChange={(skills) => setDraft((value) => ({ ...value, skills }))}
      />
      <HighlightsEditor
        value={draft.highlights}
        onChange={(highlights) =>
          setDraft((value) => ({ ...value, highlights }))
        }
      />
      <FilesInput
        stored={context.files}
        value={draft.files}
        onChange={(files) => setDraft((value) => ({ ...value, files }))}
      />
    </EditBlock>
  );
}
