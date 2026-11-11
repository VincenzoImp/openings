import { useState } from "react";
import {
  api,
  policySections,
  type Policy,
  type PolicyItem,
  type PolicySection,
  type PolicySectionName,
} from "../../api";
import { Button, Statement, StatementList } from "../../design";
import { ConfirmDialog } from "../../library/common";
import { useWorkspace } from "../../state";
import { ItemForm } from "./ItemForm";
import {
  ItemBody,
  ItemCaption,
  ItemTags,
  MoveSelect,
  Unconfirmed,
} from "./ItemRow";
import { bodyOf, draftOf, sectionWords, type ItemDraft } from "./model";

export type Outcome = "ok" | "conflict" | "error";
/** Send one policy write; the screen applies the answer or reads the policy again. */
export type Run = (
  call: () => Promise<unknown>,
  message: string,
  /** True when a form keeps the unsaved text and reports a conflict itself. */
  form?: boolean,
) => Promise<Outcome>;

interface Editing {
  /** The id of the item, or "new". */
  id: string;
  draft: ItemDraft;
  conflict?: string;
}
const CHANGED =
  "This section changed in another session. Your text is kept: check the list, then save again.";
const REMOVED =
  "This item was removed in another session. Your text is kept: saving adds it again.";

/** One section of the policy: its statements, and the form that adds or edits one. */
export function SectionCard({
  section,
  policy,
  busy,
  run,
}: {
  section: PolicySection;
  policy: Policy;
  busy: boolean;
  run: Run;
}) {
  const name = section.section;
  const words = sectionWords[name];
  const { notify } = useWorkspace();
  const [editing, setEditing] = useState<Editing | null>(null);
  const [removing, setRemoving] = useState<PolicyItem | null>(null);
  const expected = { expected_version: section.version };
  const edited = section.items.find((item) => item.id === editing?.id);
  // The item under the form disappeared: the form stays and adds it again.
  const orphan = editing && editing.id !== "new" && !edited;

  async function save() {
    if (!editing) return;
    let body;
    try {
      body = bodyOf(editing.draft, name, policy.signals);
    } catch (cause) {
      return notify((cause as Error).message, true);
    }
    const outcome = await run(
      () =>
        edited
          ? api(`/policy/items/${edited.id}`, "PATCH", { ...expected, ...body })
          : api(`/policy/${name}/items`, "POST", { ...expected, ...body }),
      edited ? "Saved." : `Added to ${policySections[name]}.`,
      true,
    );
    if (outcome === "ok") setEditing(null);
    else if (outcome === "conflict")
      setEditing({ ...editing, conflict: CHANGED });
  }
  const act = (path: string, body: object, message: string) =>
    run(() => api(path, "POST", { ...expected, ...body }), message);
  const move = (item: PolicyItem, target: PolicySectionName) =>
    act(
      `/policy/items/${item.id}/move`,
      {
        section: target,
        target_version: policy.sections.find(
          (entry) => entry.section === target,
        )!.version,
      },
      `Moved to ${policySections[target]}.`,
    );
  const reorder = (index: number, step: -1 | 1) => {
    // The buttons stay enabled while a write runs, so focus stays on them.
    if (busy) return;
    const ids = section.items.map((item) => item.id);
    [ids[index], ids[index + step]] = [ids[index + step], ids[index]];
    return act(`/policy/${name}/reorder`, { item_ids: ids }, "Order saved.");
  };
  const form = (item?: PolicyItem) => (
    <ItemForm
      section={section}
      item={item}
      draft={editing!.draft}
      onDraft={(draft) => setEditing({ ...editing!, draft })}
      signals={policy.signals}
      conflict={orphan ? REMOVED : editing!.conflict}
      busy={busy}
      onSave={save}
      onCancel={() => setEditing(null)}
      extra={
        item &&
        !item.rule && (
          <MoveSelect
            item={item}
            disabled={busy}
            onMove={async (target) => {
              if ((await move(item, target)) === "ok") setEditing(null);
            }}
          />
        )
      }
    />
  );
  return (
    <section className="card" aria-labelledby={`policy-${name}`}>
      <header>
        <div className="grow">
          <h2 id={`policy-${name}`} tabIndex={-1}>
            {policySections[name]}
          </h2>
          <div className="caption">
            {section.description} · version {section.version}
          </div>
        </div>
        <Button
          size="sm"
          disabled={!!editing}
          onClick={() => setEditing({ id: "new", draft: draftOf() })}
        >
          {words.add}
        </Button>
      </header>
      {section.items.length || editing ? (
        <StatementList label={`${policySections[name]} items`}>
          {section.items.map((item, index) => (
            <Statement
              key={item.id}
              name={item.label}
              editing={editing?.id === item.id}
              disabled={!!editing}
              onUp={index ? () => reorder(index, -1) : undefined}
              onDown={
                index < section.items.length - 1
                  ? () => reorder(index, 1)
                  : undefined
              }
              label={item.label}
              tags={<ItemTags item={item} signals={policy.signals} />}
              caption={<ItemCaption item={item} />}
              actions={
                <>
                  <Button
                    size="sm"
                    variant="quiet"
                    aria-label={`Edit ${item.label}`}
                    disabled={!!editing}
                    onClick={() =>
                      setEditing({ id: item.id, draft: draftOf(item) })
                    }
                  >
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="quiet danger"
                    aria-label={`Remove ${item.label}`}
                    disabled={busy}
                    onClick={() => setRemoving(item)}
                  >
                    Remove
                  </Button>
                </>
              }
            >
              {editing?.id === item.id ? (
                form(item)
              ) : (
                <>
                  <ItemBody
                    item={item}
                    signals={policy.signals}
                    signalsApplied={policy.signals_applied}
                    busy={busy}
                    onEnabled={(enabled) =>
                      run(
                        () =>
                          api(`/policy/items/${item.id}`, "PATCH", {
                            ...expected,
                            enabled,
                          }),
                        enabled
                          ? "The rule is on. It applies once signals are collected."
                          : "The rule is off.",
                      )
                    }
                  />
                  {!item.confirmed && (
                    <Unconfirmed
                      item={item}
                      busy={busy || !!editing}
                      onConfirm={() =>
                        act(
                          `/policy/items/${item.id}/confirm`,
                          {},
                          "Confirmed.",
                        )
                      }
                      onMove={(target) => move(item, target)}
                    />
                  )}
                </>
              )}
            </Statement>
          ))}
          {editing && !edited && (
            <Statement name="the new item" editing movable={false}>
              {form()}
            </Statement>
          )}
        </StatementList>
      ) : (
        <p className="body muted">{words.empty}</p>
      )}
      {removing && (
        <ConfirmDialog
          title={`Remove this ${words.item}?`}
          confirm={`Remove ${words.item}`}
          keep={`Keep ${words.item}`}
          onClose={() => setRemoving(null)}
          onConfirm={async () => {
            await run(
              () =>
                api(
                  `/policy/items/${removing.id}?expected_version=${section.version}`,
                  "DELETE",
                ),
              "Removed.",
            );
            setRemoving(null);
          }}
        >
          <p>
            <strong>{removing.label}</strong> is removed from{" "}
            {policySections[name]}. Applications that were already prepared keep
            the copy they were written under.
          </p>
        </ConfirmDialog>
      )}
    </section>
  );
}
