import { useState } from "react";
import { api, careerDates, knowledgeKinds, type Knowledge } from "../../api";
import {
  Banner,
  Button,
  Dialog,
  Field,
  List,
  ListRow,
  Tag,
} from "../../design";
import { useWorkspace } from "../../state";

interface Preview {
  knowledge: Partial<Knowledge>[];
  profile?: Record<string, unknown>;
  expected_profile_version?: number;
  warnings: string[];
}
const EXAMPLE = "career.json";

/** Import entries from text, Markdown or JSON: preview first, then confirm. */
export function ImportDialog({ onClose }: { onClose: () => void }) {
  const { mutate, pending, notify } = useWorkspace();
  const [raw, setRaw] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const inspect = () =>
    mutate(
      async () =>
        setPreview(
          await api<Preview>("/career/import/preview", "POST", { text: raw }),
        ),
      "Import preview ready.",
    );
  async function apply() {
    if (!preview) return;
    if (
      await mutate(
        () =>
          api("/career/import", "POST", {
            knowledge: preview.knowledge,
            profile: preview.profile,
            expected_profile_version: preview.expected_profile_version,
          }),
        "Career information imported.",
      )
    )
      onClose();
  }
  return (
    <Dialog title="Import entries" onClose={onClose}>
      <form
        className="stack"
        data-dirty={raw ? "true" : "false"}
        onSubmit={(event) => {
          event.preventDefault();
          if (!preview) void inspect();
        }}
      >
        {!preview ? (
          <>
            <p className="muted">
              Paste text, Markdown or JSON and look at the result before
              anything is added. Profile fields change only after you confirm.{" "}
              <a href={`/api/v1/examples/${EXAMPLE}`} download={EXAMPLE}>
                Download an example
              </a>
              .
            </p>
            <Field label="Text or JSON">
              <textarea
                name="import_text"
                rows={10}
                value={raw}
                onChange={(event) => setRaw(event.target.value)}
                placeholder='[{"kind":"project","title":"Example project","narrative":"What you built and learned…"}]'
              />
            </Field>
            <Field label="Or choose a text or JSON file">
              <input
                type="file"
                accept=".txt,.md,.json"
                onChange={async (event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  if (file.size > 2_000_000)
                    return notify("Use a text file below 2 MB.", true);
                  setRaw(await file.text());
                }}
              />
            </Field>
            <div className="row">
              <Button
                type="button"
                variant="primary"
                disabled={pending || !raw.trim()}
                onClick={inspect}
              >
                Preview import
              </Button>
              <Button type="button" onClick={onClose}>
                Cancel
              </Button>
            </div>
          </>
        ) : (
          <>
            {preview.warnings?.map((warning, index) => (
              <Banner tone="info" key={index}>
                {warning}
              </Banner>
            ))}
            {preview.profile && (
              <section aria-labelledby="import-profile-title">
                <h3 id="import-profile-title">Profile fields to update</h3>
                <dl className="dl">
                  {Object.entries(preview.profile).map(([key, value]) => (
                    <div key={key} style={{ display: "contents" }}>
                      <dt>{key.replaceAll("_", " ")}</dt>
                      <dd>
                        {typeof value === "string"
                          ? value
                          : Array.isArray(value)
                            ? `${value.length} entries`
                            : `${Object.keys(value || {}).length} fields`}
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            )}
            <div className="card preview-list">
              <List label="Entries to add">
                {preview.knowledge.map((entry, index) => (
                  <ListRow
                    key={index}
                    title={entry.title}
                    meta={
                      <>
                        {[entry.organization, careerDates(entry.dates)]
                          .filter(Boolean)
                          .join(" · ")}
                        {entry.narrative && (
                          <div>
                            {entry.narrative.slice(0, 180)}
                            {entry.narrative.length > 180 ? "…" : ""}
                          </div>
                        )}
                      </>
                    }
                  >
                    <Tag>
                      {entry.kind
                        ? knowledgeKinds[entry.kind] || entry.kind
                        : "Other"}
                    </Tag>
                  </ListRow>
                ))}
              </List>
            </div>
            <div className="row">
              <Button
                type="button"
                variant="primary"
                disabled={pending}
                onClick={apply}
              >
                Confirm import
              </Button>
              <Button type="button" onClick={() => setPreview(null)}>
                Back
              </Button>
            </div>
          </>
        )}
      </form>
    </Dialog>
  );
}
