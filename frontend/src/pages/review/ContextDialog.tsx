import { useState, type FormEvent } from "react";
import {
  api,
  careerEntryLabel,
  download,
  newId,
  type Application,
  type Claim,
  type Json,
  type Knowledge,
  type ListResult,
  type Template,
} from "../../api";
import { Button, Dialog, ErrorBanner, Field, Loading } from "../../design";
import { useResource, useWorkspace } from "../../state";

const NONE = { items: [], total: 0 };

/** Pick some of a long list: filter, select or clear what matches, tick one by one. */
function Choices({
  label,
  items,
  selected,
  onChange,
  limit,
  hint,
}: {
  label: string;
  items: { id: string; label: string }[];
  selected: string[];
  onChange: (ids: string[]) => void;
  limit: number;
  hint: string;
}) {
  const [query, setQuery] = useState("");
  const visible = items.filter((item) =>
    item.label.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <fieldset className="field choices">
      <legend>
        {label} · {selected.length} selected
      </legend>
      <p className="hint">{hint}</p>
      <div className="row">
        <input
          className="input grow"
          aria-label={`Find ${label.toLowerCase()}`}
          placeholder={`Find ${label.toLowerCase()}`}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <Button
          type="button"
          size="sm"
          data-dirty-control="true"
          disabled={selected.length >= limit}
          onClick={() =>
            onChange(
              [
                ...new Set([...selected, ...visible.map((item) => item.id)]),
              ].slice(0, limit),
            )
          }
        >
          Select matching
        </Button>
        <Button
          type="button"
          size="sm"
          variant="quiet"
          data-dirty-control="true"
          onClick={() =>
            onChange(
              selected.filter((id) => !visible.some((item) => item.id === id)),
            )
          }
        >
          Clear matching
        </Button>
      </div>
      <ul className="picks list preview-list">
        {visible.map((item) => (
          <li key={item.id}>
            <label className="toggle">
              <input
                type="checkbox"
                checked={selected.includes(item.id)}
                disabled={
                  !selected.includes(item.id) && selected.length >= limit
                }
                onChange={(event) =>
                  onChange(
                    event.target.checked
                      ? [...selected, item.id]
                      : selected.filter((id) => id !== item.id),
                  )
                }
              />
              <span>{item.label}</span>
            </label>
          </li>
        ))}
        {!visible.length && <li className="muted">Nothing matches.</li>}
      </ul>
    </fieldset>
  );
}

/**
 * Prepare a frozen copy of the record for the agent: the job, the templates,
 * the Career entries and approved claims, the policy and instructions. It is
 * saved and downloaded; it never changes afterwards.
 */
export function ContextDialog({
  application,
  onClose,
}: {
  application: Application;
  onClose: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  const templates = useResource<ListResult<Template>>(
    "/templates?summary=true",
    NONE,
    true,
  );
  const knowledge = useResource<ListResult<Knowledge>>(
    "/career/knowledge?summary=true",
    NONE,
    true,
  );
  const claims = useResource<ListResult<Claim>>(
    "/career/claims?summary=true&approved=true",
    NONE,
    true,
  );
  const [templateIds, setTemplateIds] = useState<string[]>([]);
  const [pickEntries, setPickEntries] = useState(false);
  const [pickClaims, setPickClaims] = useState(false);
  const [entryIds, setEntryIds] = useState<string[] | null>(null);
  const [claimIds, setClaimIds] = useState<string[] | null>(null);
  const loading = templates.loading || knowledge.loading || claims.loading;
  const failed = [templates, knowledge, claims].find((part) => part.error);
  const entries =
    entryIds ?? knowledge.data.items.slice(0, 500).map((item) => item.id);
  const available = claims.data.items.filter(
    (claim) => !pickEntries || entries.includes(claim.knowledge_id),
  );
  const chosenClaims = (
    claimIds ?? available.slice(0, 1000).map((claim) => claim.id)
  ).filter((id) => available.some((claim) => claim.id === id));
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading || failed) return;
    const note = String(new FormData(event.currentTarget).get("note") || "");
    const ok = await mutate(async () => {
      const context = await api<Json>("/contexts", "POST", {
        application_id: application.id,
        template_ids: templateIds,
        ...(pickEntries ? { knowledge_ids: entries } : {}),
        ...(pickClaims ? { claim_ids: chosenClaims } : {}),
        note,
        idempotency_key: newId(),
      });
      download(`context-${context.id}.json`, JSON.stringify(context, null, 2));
    }, "Frozen copy saved and downloaded.");
    if (ok) onClose();
  }
  return (
    <Dialog
      title="Prepare a frozen copy for your agent"
      className="wide"
      onClose={onClose}
    >
      <form className="stack" onSubmit={save}>
        <p className="muted">
          The copy keeps the exact record of this moment. Your agent writes the
          documents from it; nothing here submits the application.
        </p>
        {failed && (
          <ErrorBanner message={failed.error!} retry={failed.reload} />
        )}
        {loading ? (
          <Loading label="Loading your record…" />
        ) : (
          <>
            <Choices
              label="Templates"
              limit={20}
              items={templates.data.items.map((template) => ({
                id: template.id,
                label: `${template.name} · ${template.kind === "cv" ? "CV" : "Letter"}`,
              }))}
              selected={templateIds}
              onChange={setTemplateIds}
              hint="Up to 20. With none selected, your default templates are used."
            />
            <label className="toggle">
              <input
                type="checkbox"
                checked={pickEntries}
                onChange={(event) => setPickEntries(event.target.checked)}
              />
              <span>Choose the Career entries</span>
            </label>
            {pickEntries && (
              <Choices
                label="Career entries"
                limit={500}
                items={knowledge.data.items.map((item) => ({
                  id: item.id,
                  label: careerEntryLabel(item),
                }))}
                selected={entries}
                onChange={setEntryIds}
                hint="Every entry starts selected. Claims of an entry left out are left out too."
              />
            )}
            <label className="toggle">
              <input
                type="checkbox"
                checked={pickClaims}
                onChange={(event) => setPickClaims(event.target.checked)}
              />
              <span>Choose the approved claims</span>
            </label>
            {pickClaims && (
              <Choices
                label="Approved claims"
                limit={1000}
                items={available.map((claim) => ({
                  id: claim.id,
                  label: `${claim.knowledge_title || "Career entry"}: ${claim.text_preview || claim.text}`,
                }))}
                selected={chosenClaims}
                onChange={setClaimIds}
                hint="An empty selection gives the agent no claim on purpose."
              />
            )}
            <Field label="Instructions for this copy" hint="Optional.">
              <textarea name="note" rows={3} maxLength={20000} />
            </Field>
            {!templates.data.items.length && (
              <p className="muted">Add a template in Templates first.</p>
            )}
          </>
        )}
        <div className="row">
          <Button
            variant="primary"
            disabled={
              pending || loading || !!failed || !templates.data.items.length
            }
          >
            Save and download
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
