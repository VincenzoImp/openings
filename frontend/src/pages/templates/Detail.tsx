import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  api,
  date,
  download,
  fileUrl,
  version,
  type Template,
} from "../../api";
import { Button, EmptyState, Field, Tabs, Tag } from "../../design";
import { Assets, isPdf, useAssets } from "../../library/Assets";
import { ConfirmDialog, fileSize, plural } from "../../library/common";
import { useWorkspace } from "../../state";
import { TemplateSettings, kindLabels } from "./Dialogs";
import { RulesTab } from "./Rules";

// The tab names of earlier versions still open the right tab.
const TAB_ALIASES: Record<string, string> = {
  instructions: "rules",
  "": "source",
};
const fileName = (template: Template) =>
  (template.kind === "resume" ? "cv" : "letter") + ".tex";

function SourceTab({ template }: { template: Template }) {
  const { mutate, pending, notify } = useWorkspace();
  const [source, setSource] = useState(template.tex);
  const picker = useRef<HTMLInputElement>(null);
  const form = useRef<HTMLFormElement>(null);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await mutate(
      () =>
        api(
          `/templates/${template.id}`,
          "PATCH",
          version(template, { tex: source }),
        ),
      "Source saved. Applications that were already prepared keep theirs.",
    );
  }
  const lines = source ? source.split("\n").length : 0;
  return (
    <form ref={form} onSubmit={save}>
      <div className="body stack">
        <div className="spread wrap">
          <div>
            <strong className="mono">{fileName(template)}</strong>{" "}
            <span className="caption">
              · {plural(lines, "line")} ·{" "}
              {fileSize(new TextEncoder().encode(source).length)}
            </span>
          </div>
          <div className="row">
            <input
              ref={picker}
              type="file"
              accept=".tex,.txt"
              hidden
              aria-label="Source file to load"
              onChange={async (event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (!file) return;
                if (file.size > 1_000_000)
                  return notify("Use a source file smaller than 1 MB.", true);
                setSource(await file.text());
                // Loading a file is an edit of this form.
                if (form.current) form.current.dataset.dirty = "true";
              }}
            />
            <Button
              type="button"
              size="sm"
              onClick={() => picker.current?.click()}
            >
              Replace from a file
            </Button>
            <Button
              type="button"
              size="sm"
              variant="quiet"
              onClick={() =>
                download(fileName(template), source, "application/x-tex")
              }
            >
              Download
            </Button>
          </div>
        </div>
        <Field
          label="LaTeX source"
          hint="The workspace stores this text. Your agent fills and compiles it on its own machine."
        >
          <textarea
            className="code"
            name="tex"
            spellCheck={false}
            value={source}
            onChange={(event) => setSource(event.target.value)}
          />
        </Field>
      </div>
      <footer>
        <span className="muted grow">
          {source
            ? "Applications that were already prepared keep the source they froze."
            : "No source yet: the agent cannot build a document from this template."}
        </span>
        <Button variant="primary" size="sm" disabled={pending}>
          Save source
        </Button>
      </footer>
    </form>
  );
}

function PreviewTab({ template }: { template: Template }) {
  const { data } = useAssets("template", template.id);
  const pdf = data.items.find(isPdf);
  const [url, setUrl] = useState("");
  useEffect(() => {
    let active = true;
    setUrl("");
    if (pdf)
      fileUrl(pdf)
        .then((value) => active && setUrl(value))
        .catch(() => {});
    return () => {
      active = false;
    };
  }, [pdf?.id]);
  if (!pdf)
    return (
      <EmptyState title="No preview yet">
        The workspace does not compile TeX. When your agent compiles a sample of
        this template, add the PDF under Assets and it is shown here.
      </EmptyState>
    );
  return (
    <div className="body stack">
      <p className="caption">
        <span className="mono">{pdf.name}</span>, added {date(pdf.created_at)}.
        It was compiled outside the workspace and may be older than the source.
      </p>
      {url && (
        <iframe
          title={`Sample of ${template.name}`}
          className="frame"
          src={`${url}${url.includes("?") ? "&" : "?"}inline=true#toolbar=0`}
          referrerPolicy="no-referrer"
        />
      )}
    </div>
  );
}

/** One template: its source, rules, assets and an uploaded sample. */
export function TemplateDetail({
  template,
  tab,
  onTab,
  onRemoved,
}: {
  template: Template;
  tab: string;
  onTab: (tab: string) => void;
  onRemoved: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  const assets = useAssets("template", template.id);
  const [settings, setSettings] = useState(false);
  const [removing, setRemoving] = useState(false);
  const kind = kindLabels[template.kind];
  const shown = TAB_ALIASES[tab] ?? tab;
  const current = ["source", "rules", "assets", "preview"].includes(shown)
    ? shown
    : "source";
  return (
    <section className="card detail" aria-labelledby="template-title">
      <header>
        <div className="grow">
          <div className="row">
            <h2 id="template-title">{template.name}</h2>
            {template.is_default && <Tag tone="ready">Default {kind}</Tag>}
          </div>
          <div className="caption">
            {kind} · version {template.version} · changed{" "}
            {date(template.updated_at)}
          </div>
        </div>
        <Button size="sm" variant="quiet" onClick={() => setSettings(true)}>
          Rename
        </Button>
        {!template.is_default && (
          <Button
            size="sm"
            variant="quiet"
            disabled={pending}
            onClick={() =>
              mutate(
                () =>
                  api(
                    `/templates/${template.id}`,
                    "PATCH",
                    version(template, { is_default: true }),
                  ),
                `${template.name} is the default ${kind}.`,
              )
            }
          >
            Make default
          </Button>
        )}
        <Button
          size="sm"
          variant="quiet danger"
          onClick={() => setRemoving(true)}
        >
          Delete
        </Button>
      </header>
      <Tabs
        id="template"
        label={template.name}
        value={current}
        onChange={onTab}
        items={[
          { id: "source", label: "Source" },
          { id: "rules", label: "Guidance" },
          { id: "assets", label: "Assets", count: assets.data.total },
          { id: "preview", label: "Preview" },
        ]}
      >
        {current === "source" ? (
          <SourceTab key={template.version} template={template} />
        ) : current === "rules" ? (
          <RulesTab key={template.version} template={template} />
        ) : current === "assets" ? (
          <Assets
            ownerType="template"
            ownerId={template.id}
            empty="No assets yet. Add the class file, fonts and images the source loads."
            note="Assets are stored once and shared by every application that uses this template."
          />
        ) : (
          <PreviewTab template={template} />
        )}
      </Tabs>
      {settings && (
        <TemplateSettings
          template={template}
          onClose={() => setSettings(false)}
        />
      )}
      {removing && (
        <ConfirmDialog
          title="Remove this template?"
          confirm="Remove template"
          keep="Keep template"
          onClose={() => setRemoving(false)}
          onConfirm={async () => {
            if (
              await mutate(
                () =>
                  api(
                    `/templates/${template.id}?expected_version=${template.version}`,
                    "DELETE",
                  ),
                "Template removed.",
              )
            ) {
              setRemoving(false);
              onRemoved();
            }
          }}
        >
          <p>
            <strong>{template.name}</strong> and its assets are removed.
            Applications that were already prepared keep the template they
            froze.
          </p>
        </ConfirmDialog>
      )}
    </section>
  );
}
