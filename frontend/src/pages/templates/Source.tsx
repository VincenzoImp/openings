import { useEffect, useRef, useState } from "react";
import { FileCode2, Pencil } from "lucide-react";
import { Button } from "../../ui/Button";
import { CodeEditor, CodeView } from "../../ui/CodeView";
import { EmptyState } from "../../ui/Page";
import { LeaveDialog, SaveBar } from "../../ui/ReadEdit";
import { isModKey } from "../../ui/keys";
import { useToast } from "../../ui/Toast";
import { ConflictNotice } from "../../query/ConflictNotice";
import { isConflict } from "../../query/mutation";
import { useUpdateTemplate, type Template } from "../../query/templates";
import { shownSource } from "./model";

const fileName = (template: Template) =>
  `${template.kind === "letter" ? "letter" : "cv"}.tex`;

/**
 * The LaTeX source: a read-only code view with line numbers; Edit source
 * turns it into an editor with a sticky Save/Cancel bar. The template's
 * guidance, written through the API, is shown below it.
 */
export function SourceTab({
  template,
  onDirty,
}: {
  template: Template;
  onDirty: (dirty: boolean) => void;
}) {
  const stored = template.tex ?? "";
  const [draft, setDraft] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const toast = useToast();
  const update = useUpdateTemplate(template, () => setDraft(null));
  const editButton = useRef<HTMLButtonElement>(null);
  const dirty = draft !== null && draft !== stored;
  useEffect(() => onDirty(dirty), [dirty, onDirty]);
  useEffect(() => () => onDirty(false), [onDirty]);
  const shown = shownSource(stored);
  const lines = shown ? shown.split("\n").length : 0;
  const close = () => {
    setDraft(null);
    requestAnimationFrame(() => editButton.current?.focus());
  };
  const cancel = () => (dirty ? setAsking(true) : close());
  const save = () => {
    if (draft === null || !dirty || update.isPending) return;
    update.mutate(
      { tex: draft },
      {
        onSuccess: () => {
          close();
          toast.show({ tone: "success", message: "Source saved" });
        },
        onError: (cause) => {
          if (isConflict(cause)) return;
          toast.show({
            tone: "error",
            message: cause instanceof Error ? cause.message : "Not saved.",
          });
        },
      },
    );
  };
  if (draft !== null)
    return (
      <form
        className="tpl-source-edit"
        data-unguarded=""
        aria-label="Edit source"
        onSubmit={(event) => {
          event.preventDefault();
          save();
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && isModKey(event.nativeEvent)) {
            event.preventDefault();
            save();
          } else if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            cancel();
          }
        }}
      >
        {update.conflict && (
          <ConflictNotice
            onReload={() => void update.reload()}
            onKeepEditing={() => void update.keepEditing()}
          />
        )}
        <div className="tpl-bar">
          <span className="tpl-file">{fileName(template)}</span>
          <span className="tpl-bar-note">{draft.split("\n").length} lines</span>
        </div>
        <CodeEditor
          value={draft}
          aria-label="LaTeX source"
          autoFocus
          onChange={(event) => setDraft(event.target.value)}
        />
        {dirty ? (
          <SaveBar changes={1} saving={update.isPending} onCancel={cancel} />
        ) : (
          <div className="tpl-idle">
            <Button variant="ghost" onClick={close}>
              Cancel
            </Button>
          </div>
        )}
        <LeaveDialog
          open={asking}
          changes={1}
          onStay={() => setAsking(false)}
          onLeave={() => {
            setAsking(false);
            close();
          }}
        />
      </form>
    );
  return (
    <div className="tpl-source">
      {stored ? (
        <>
          <div className="tpl-bar">
            <span className="tpl-file">{fileName(template)}</span>
            <span className="tpl-bar-note">
              {lines === 1 ? "1 line" : `${lines} lines`}
            </span>
            <span className="tpl-bar-space" />
            <Button
              ref={editButton}
              size="sm"
              icon={Pencil}
              onClick={() => setDraft(stored)}
            >
              Edit source
            </Button>
          </div>
          <CodeView code={shown} label="LaTeX source" />
        </>
      ) : (
        <EmptyState
          icon={FileCode2}
          title="No source yet"
          actions={
            <Button
              ref={editButton}
              variant="primary"
              icon={Pencil}
              onClick={() => setDraft("")}
            >
              Edit source
            </Button>
          }
        >
          Paste the LaTeX your CV or letter is built from.
        </EmptyState>
      )}
      {template.guidance?.trim() && (
        <section className="tpl-guidance" aria-label="Guidance">
          <h3>Guidance</h3>
          <p>{template.guidance}</p>
          <p className="tpl-guidance-note">
            Written through the API. Writing rules live in{" "}
            <a href="#preferences">Preferences</a>.
          </p>
        </section>
      )}
    </div>
  );
}
