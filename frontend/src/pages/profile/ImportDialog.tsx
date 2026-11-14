// Import CV text: paste text or Markdown (or drop a .txt/.md file), look at
// the entries and highlights found, and add them only on confirmation. The
// career import preview checks the entries; the header fills only the empty
// fields of the Profile.
import { useState } from "react";
import { Upload } from "lucide-react";
import { Button } from "../../ui/Button";
import { Drawer } from "../../ui/Dialog";
import { Field, Textarea } from "../../ui/Field";
import { Icon } from "../../ui/Icon";
import { LeaveDialog } from "../../ui/ReadEdit";
import { useToast } from "../../ui/Toast";
import { useApiMutation } from "../../query/mutation";
import { cached, writes, type EntryInput } from "./data";
import { KINDS, formatDates, type Kind } from "./model";
import { EXAMPLE, parseCv } from "./parse";
import { Failure } from "./save";

const FIELDS = ["name", "headline", "location", "email", "phone", "summary"];

interface Preview {
  header: Record<string, unknown>;
  entries: { input: EntryInput; highlights: string[] }[];
  version: number;
  notes: string[];
}

async function inspect(raw: string): Promise<Preview> {
  const { header, entries } = parseCv(raw);
  const profile = cached.profile();
  // Only what the Profile does not have yet.
  const patch: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(header))
    if (
      FIELDS.includes(key)
        ? !String(profile?.[key] ?? "").trim()
        : !profile?.links?.length
    )
      patch[key] = value;
  // Entries the reader found are checked as JSON; other text is kept whole.
  const result = await writes.previewImport(
    entries.length
      ? JSON.stringify({
          knowledge: entries.map(({ highlights, location, ...entry }) => ({
            ...entry,
            metadata: location ? { location } : {},
          })),
        })
      : raw,
  );
  return {
    header: patch,
    entries: (result.knowledge as EntryInput[]).map((input, index) => ({
      input,
      highlights: entries[index]?.highlights ?? [],
    })),
    version: profile?.version ?? 0,
    notes: entries.length ? [] : (result.warnings as string[]),
  };
}

async function add({ header, entries, version }: Preview) {
  const filled = Object.keys(header).length > 0;
  const result = await writes.import({
    knowledge: entries.map((entry) => entry.input),
    ...(filled ? { profile: header, expected_profile_version: version } : {}),
  });
  // The highlights the person read in the preview are their own words.
  for (const [index, item] of result.items.entries())
    for (const [position, text] of entries[index].highlights.entries())
      await writes.createHighlight({
        knowledge_id: item.id,
        text,
        approved: true,
        always_include: false,
        position,
      });
  return result.total;
}

const count = (n: number, one: string, many = `${one}s`) =>
  `${n} ${n === 1 ? one : many}`;

export function ImportDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const toast = useToast();
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [problem, setProblem] = useState("");
  const [over, setOver] = useState(false);
  const [asking, setAsking] = useState(false);
  const read = useApiMutation({ touches: [], mutationFn: inspect });
  const confirm = useApiMutation({ touches: ["career"], mutationFn: add });

  const close = () => {
    setText("");
    setPreview(null);
    setProblem("");
    read.reset();
    confirm.reset();
    onClose();
  };
  const leave = () => (text.trim() ? setAsking(true) : close());
  const take = async (file?: File) => {
    if (!file) return;
    if (!/\.(txt|md|markdown)$/i.test(file.name))
      return setProblem("Choose a .txt or .md file.");
    if (file.size > 2_000_000) return setProblem("Choose a file below 2 MB.");
    setProblem("");
    setText(await file.text());
  };

  const highlights =
    preview?.entries.reduce((sum, entry) => sum + entry.highlights.length, 0) ??
    0;
  const filled = Object.keys(preview?.header ?? {});

  return (
    <>
      <Drawer
        open={open}
        onClose={leave}
        title={preview ? "Check what was found" : "Import CV text"}
        className="pf-import"
        footer={
          preview ? (
            <>
              <Button variant="ghost" onClick={() => setPreview(null)}>
                Back
              </Button>
              <Button
                variant="primary"
                disabled={confirm.isPending}
                onClick={() =>
                  confirm.mutate(preview, {
                    onSuccess: (total) => {
                      toast.show({
                        message: `Imported ${count(total, "entry", "entries")}`,
                        tone: "success",
                      });
                      close();
                    },
                  })
                }
              >
                {confirm.isPending
                  ? "Adding…"
                  : `Add ${count(preview.entries.length, "entry", "entries")}`}
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" onClick={leave}>
                Cancel
              </Button>
              <Button
                variant="primary"
                disabled={!text.trim() || read.isPending}
                onClick={() => read.mutate(text, { onSuccess: setPreview })}
              >
                {read.isPending ? "Reading…" : "Preview"}
              </Button>
            </>
          )
        }
      >
        <Failure error={read.error || confirm.error} title="Not imported" />
        {!preview ? (
          <>
            <p className="pf-lead">
              Paste the text of your CV. Your agent can also read a PDF CV for
              you.
            </p>
            <Field label="CV text" error={problem || undefined}>
              <Textarea
                name="cv_text"
                rows={14}
                value={text}
                placeholder={EXAMPLE}
                onChange={(event) => setText(event.target.value)}
              />
            </Field>
            <label
              className="pf-drop"
              data-over={over || undefined}
              onDragOver={(event) => {
                event.preventDefault();
                setOver(true);
              }}
              onDragLeave={() => setOver(false)}
              onDrop={(event) => {
                event.preventDefault();
                setOver(false);
                void take(event.dataTransfer.files[0]);
              }}
            >
              <Icon icon={Upload} />
              <span>
                Drop a <b>.txt</b> or <b>.md</b> file, or <u>choose one</u>
              </span>
              <input
                type="file"
                accept=".txt,.md,.markdown"
                className="pf-hidden"
                onChange={(event) => {
                  void take(event.target.files?.[0]);
                  event.target.value = "";
                }}
              />
            </label>
          </>
        ) : (
          <>
            <p className="pf-lead">
              {count(preview.entries.length, "entry", "entries")} and{" "}
              {count(highlights, "highlight")}
              {filled.length ? " and your header" : ""}. Nothing is saved until
              you add them.
            </p>
            {preview.notes.map((note) => (
              <p className="pf-lead" key={note}>
                {note}
              </p>
            ))}
            {filled.length > 0 && (
              <div className="pf-found">
                <p className="pf-found-title">Header</p>
                <p className="pf-found-sub">
                  {filled
                    .map((key) =>
                      key === "links"
                        ? "Links"
                        : String(preview.header[key]).split("\n")[0],
                    )
                    .join(" · ")}
                </p>
              </div>
            )}
            {preview.entries.map(({ input, highlights }, index) => (
              <div className="pf-found" key={index}>
                <p className="pf-found-title">
                  {input.title}
                  <span>{KINDS[input.kind as Kind]}</span>
                </p>
                <p className="pf-found-sub">
                  {[
                    input.organization,
                    formatDates(input.dates),
                    (input.metadata as { location?: string })?.location,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                {input.narrative && (
                  <p className="pf-found-sub">{input.narrative}</p>
                )}
                {highlights.length > 0 && (
                  <ul className="pf-highlights">
                    {highlights.map((text, at) => (
                      <li key={at}>{text}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </>
        )}
      </Drawer>
      <LeaveDialog
        open={asking}
        changes={1}
        onStay={() => setAsking(false)}
        onLeave={() => {
          setAsking(false);
          close();
        }}
      />
    </>
  );
}
