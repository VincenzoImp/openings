import {
  useEffect,
  useId,
  useRef,
  useState,
  type PointerEvent,
  type ReactNode,
} from "react";
import { Plus } from "lucide-react";
import { Button } from "../../ui/Button";
import { Tag } from "../../ui/Badge";
import { ConflictNotice } from "../../query/ConflictNotice";
import type { SectionName, Statement } from "../../query/preferences";
import { Line, LineEditor } from "./Line";
import { dropIndex, reordered, scopeLabels, type SectionInfo } from "./model";

/** Which line is being written: an existing one (its index) or a new one. */
type Editing = { index: number | null; draft: Statement } | null;

export interface SectionActions {
  /** Save the statement at `index` (null: a new one at the end). */
  save: (
    index: number | null,
    original: string | null,
    draft: Statement,
  ) => Promise<boolean>;
  remove: (index: number) => void;
  move: (index: number, to: SectionName) => void;
  reorder: (from: number, to: number) => void;
}

/**
 * One section of Preferences: a heading and its statements as lines of
 * text. Hover or focus shows Edit and `…`; + Add writes a new line in place.
 * Empty, it shows two grey examples.
 */
export function PreferenceSection({
  info,
  items,
  conflict,
  actions,
  onReload,
  onKeepEditing,
  onDirty,
  children,
}: {
  info: SectionInfo;
  items: Statement[];
  conflict: boolean;
  actions: SectionActions;
  onReload: () => void;
  onKeepEditing: () => void;
  onDirty: (dirty: boolean) => void;
  children?: ReactNode;
}) {
  const id = useId();
  const writing = info.name === "writing";
  const [editing, setEditing] = useState<Editing>(null);
  // Each new line is a new editor, with its own text.
  const round = useRef(0);
  const openNew = (draft: Statement) => {
    round.current += 1;
    setEditing({ index: null, draft });
  };
  const [drag, setDrag] = useState<{ from: number; to: number } | null>(null);
  const list = useRef<HTMLUListElement>(null);
  const addButton = useRef<HTMLButtonElement>(null);
  const focusAfter = useRef<number | "add" | null>(null);
  useEffect(() => {
    const target = focusAfter.current;
    if (target === null || editing) return;
    focusAfter.current = null;
    if (target === "add") addButton.current?.focus();
    else
      list.current
        ?.querySelector<HTMLElement>(`li[data-index="${target}"]`)
        ?.focus();
  });
  // A Reload after a conflict drops the draft.
  const close = (focus: number | "add" | null) => {
    focusAfter.current = focus;
    setEditing(null);
    onDirty(false);
  };
  const shown = drag ? reordered(items, drag.from, drag.to) : items;

  function startDrag(index: number, event: PointerEvent<HTMLButtonElement>) {
    if (event.button !== 0 || !list.current) return;
    event.preventDefault();
    const rows = [
      ...list.current.querySelectorAll<HTMLElement>("li[data-index]"),
    ];
    const middles = rows.map((row) => {
      const box = row.getBoundingClientRect();
      return box.top + box.height / 2;
    });
    const handle = event.currentTarget;
    handle.setPointerCapture(event.pointerId);
    let to = index;
    setDrag({ from: index, to });
    const onMove = (move: globalThis.PointerEvent) => {
      to = dropIndex(middles, index, move.clientY);
      setDrag({ from: index, to });
    };
    let done = false;
    const onUp = () => {
      if (done) return;
      done = true;
      handle.removeEventListener("pointermove", onMove);
      handle.removeEventListener("pointerup", onUp);
      handle.removeEventListener("pointercancel", onUp);
      handle.removeEventListener("lostpointercapture", onUp);
      setDrag(null);
      if (to !== index) {
        focusAfter.current = to;
        actions.reorder(index, to);
      }
    };
    handle.addEventListener("pointermove", onMove);
    handle.addEventListener("pointerup", onUp);
    handle.addEventListener("pointercancel", onUp);
    handle.addEventListener("lostpointercapture", onUp);
  }

  const editor = (index: number | null, initial: Statement) => (
    <LineEditor
      key={index ?? `new-${round.current}`}
      initial={initial}
      writing={writing}
      adding={index === null}
      placeholder={
        index === null && !items.length ? info.examples[0].text : undefined
      }
      onDirty={onDirty}
      onCancel={() => close(index ?? "add")}
      onSave={async (draft) => {
        if (!draft.text) return close(index ?? "add");
        const original = index === null ? null : items[index].text;
        if (
          index !== null &&
          draft.text === original &&
          (!writing || draft.scope === (items[index].scope || "all"))
        )
          return close(index);
        // Shown at once; a new line opens the next one.
        if (index === null) {
          openNew({ text: "", scope: draft.scope });
          onDirty(false);
        } else close(index);
        const ok = await actions.save(index, original, draft);
        if (!ok) {
          if (index === null) openNew(draft);
          else setEditing({ index, draft });
          onDirty(true);
        }
      }}
    />
  );

  return (
    <section className="pref-section" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`} className="pref-title">
        {info.title}
      </h2>
      {conflict && (
        <div className="pref-conflict">
          <ConflictNotice
            onReload={() => {
              close(null);
              onReload();
            }}
            onKeepEditing={onKeepEditing}
          />
        </div>
      )}
      {shown.length > 0 && (
        <ul
          ref={list}
          className="pref-lines"
          aria-labelledby={`${id}-title`}
          data-dragging={drag ? "" : undefined}
        >
          {shown.map((item, index, all) =>
            editing && editing.index === index ? (
              editor(index, editing.draft)
            ) : (
              <Line
                key={`${item.text}#${all.slice(0, index).filter((other) => other.text === item.text).length}`}
                item={item}
                index={index}
                section={info.name}
                writing={writing}
                dragging={drag?.to === index}
                onEdit={() => {
                  setEditing({ index, draft: item });
                }}
                onDelete={() => {
                  focusAfter.current = Math.min(index, items.length - 2);
                  actions.remove(index);
                }}
                onMove={(to) => actions.move(index, to)}
                onStep={(step) => {
                  const to = index + step;
                  if (to < 0 || to >= items.length) return;
                  focusAfter.current = to;
                  actions.reorder(index, to);
                }}
                onDragStart={(event) => startDrag(index, event)}
              />
            ),
          )}
          {editing?.index === null && editor(null, editing.draft)}
        </ul>
      )}
      {!shown.length &&
        (editing?.index === null ? (
          <ul className="pref-lines">{editor(null, editing.draft)}</ul>
        ) : (
          <>
            <p className="pref-examples-label" aria-hidden="true">
              Nothing yet. For example:
            </p>
            <ul
              className="pref-examples"
              aria-label={`Examples for ${info.title}`}
            >
              {info.examples.map((example) => (
                <li key={example.text} className="pref-line">
                  <span className="pref-lead">
                    <span className="pref-bullet" aria-hidden="true" />
                  </span>
                  <p className="pref-text">{example.text}</p>
                  {writing && (
                    <span className="pref-scope">
                      <Tag>{scopeLabels[example.scope ?? "all"]}</Tag>
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </>
        ))}
      {editing?.index !== null && (
        <Button
          ref={addButton}
          variant="ghost"
          size="sm"
          icon={Plus}
          className="pref-add"
          aria-label={`Add to ${info.title}`}
          onClick={() => openNew({ text: "", scope: "all" })}
        >
          Add
        </Button>
      )}
      {children}
    </section>
  );
}
