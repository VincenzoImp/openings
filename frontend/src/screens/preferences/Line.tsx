import {
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";
import { Ellipsis, GripVertical, Pencil, Trash2 } from "lucide-react";
import { Button, IconButton, Segmented, Tag, type MenuEntry } from "../../ui";
import { SheetMenu } from "../../ui";
import type { Scope, SectionName, Statement } from "../../query/preferences";
import { SCOPES, SECTIONS, itemName, scopeLabels } from "./model";

/** A statement at rest: text only; its actions appear on hover or focus. */
export function Line({
  item,
  index,
  section,
  writing,
  dragging,
  onEdit,
  onDelete,
  onMove,
  onStep,
  onDragStart,
}: {
  item: Statement;
  index: number;
  section: SectionName;
  writing: boolean;
  dragging: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onMove: (to: SectionName) => void;
  /** Move one place up (-1) or down (1). */
  onStep: (step: -1 | 1) => void;
  onDragStart: (event: PointerEvent<HTMLButtonElement>) => void;
}) {
  const name = itemName(item.text);
  const menu: MenuEntry[] = [
    {
      heading: "Move to",
      items: SECTIONS.filter((other) => other.name !== section).map(
        (other) => ({
          id: other.name,
          label: other.title,
          onSelect: () => onMove(other.name),
        }),
      ),
    },
    "separator",
    {
      id: "delete",
      label: "Delete",
      icon: Trash2,
      kbd: "⌫",
      danger: true,
      onSelect: onDelete,
    },
  ];
  function onKeyDown(event: KeyboardEvent<HTMLLIElement>) {
    if (event.target !== event.currentTarget) return;
    const key = event.key;
    if (event.altKey && (key === "ArrowUp" || key === "ArrowDown")) {
      event.preventDefault();
      onStep(key === "ArrowUp" ? -1 : 1);
      return;
    }
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    if (key === "Enter" || key === "e") {
      event.preventDefault();
      onEdit();
    } else if (key === "Delete" || key === "Backspace") {
      event.preventDefault();
      onDelete();
    } else if (["ArrowUp", "ArrowDown", "j", "k"].includes(key)) {
      event.preventDefault();
      const lines = [
        ...(event.currentTarget
          .closest(".prefs")
          ?.querySelectorAll<HTMLElement>("li.pref-line[tabindex]") ?? []),
      ];
      const at = lines.indexOf(event.currentTarget);
      const next = key === "ArrowUp" || key === "k" ? at - 1 : at + 1;
      lines[next]?.focus();
    }
  }
  return (
    <li
      className="pref-line"
      tabIndex={0}
      data-index={index}
      data-dragging={dragging || undefined}
      aria-keyshortcuts="Enter Delete Alt+ArrowUp Alt+ArrowDown"
      onKeyDown={onKeyDown}
      onDoubleClick={onEdit}
    >
      <span className="pref-lead">
        <span className="pref-bullet" aria-hidden="true" />
        <button
          type="button"
          className="pref-grip"
          tabIndex={-1}
          aria-label={`Reorder “${name}”`}
          title="Drag to reorder (Alt+↑ / Alt+↓)"
          onPointerDown={onDragStart}
          onKeyDown={(event) => {
            if (event.key === "ArrowUp" || event.key === "ArrowDown") {
              event.preventDefault();
              onStep(event.key === "ArrowUp" ? -1 : 1);
            }
          }}
        >
          <GripVertical size={14} strokeWidth={1.75} aria-hidden="true" />
        </button>
      </span>
      <p className="pref-text">{item.text}</p>
      {writing && (
        <span className="pref-scope">
          <Tag>{scopeLabels[(item.scope as Scope) || "all"]}</Tag>
        </span>
      )}
      <span className="pref-actions">
        <IconButton
          icon={Pencil}
          label={`Edit “${name}”`}
          shortcut="Enter"
          size="sm"
          tooltip="above"
          onClick={onEdit}
        />
        <SheetMenu
          label={`Statement “${name}”`}
          items={menu}
          trigger={(props) => (
            <IconButton
              {...props}
              icon={Ellipsis}
              label={`More for “${name}”`}
              size="sm"
              tooltip="none"
            />
          )}
        />
      </span>
    </li>
  );
}

/**
 * A statement being written: the line becomes a text field in place, with
 * All · CV · Letter for a writing rule. Enter saves (and, when adding, opens
 * the next line); Esc cancels.
 */
export function LineEditor({
  initial,
  writing,
  adding,
  placeholder,
  onSave,
  onCancel,
  onDirty,
}: {
  initial: Statement;
  writing: boolean;
  adding: boolean;
  placeholder?: string;
  onSave: (draft: Statement) => void;
  onCancel: () => void;
  onDirty: (dirty: boolean) => void;
}) {
  const [text, setText] = useState(initial.text);
  const [scope, setScope] = useState<Scope>((initial.scope as Scope) || "all");
  const field = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const el = field.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [text]);
  useLayoutEffect(() => {
    const el = field.current;
    el?.focus();
    el?.setSelectionRange(el.value.length, el.value.length);
  }, []);
  const changed =
    text.trim() !== initial.text.trim() ||
    (writing && scope !== ((initial.scope as Scope) || "all"));
  const save = () => onSave({ text: text.trim(), scope });
  return (
    <li className="pref-line" data-editing="">
      <form
        className="pref-edit"
        data-unguarded=""
        aria-label={adding ? "New statement" : "Edit statement"}
        onSubmit={(event) => {
          event.preventDefault();
          save();
        }}
      >
        <textarea
          ref={field}
          className="pref-input"
          rows={1}
          value={text}
          maxLength={2000}
          aria-label="Statement"
          placeholder={placeholder}
          onChange={(event) => {
            setText(event.target.value);
            onDirty(
              event.target.value.trim() !== initial.text.trim() ||
                (writing && scope !== ((initial.scope as Scope) || "all")),
            );
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              save();
            } else if (event.key === "Escape") {
              event.preventDefault();
              event.stopPropagation();
              onCancel();
            }
          }}
        />
        <div className="pref-editbar">
          {writing && (
            <Segmented<Scope>
              label="Applies to"
              options={SCOPES}
              value={scope}
              onChange={(value) => {
                setScope(value);
                onDirty(true);
                field.current?.focus();
              }}
            />
          )}
          <span className="pref-edithint" aria-hidden="true">
            ↵ to save · Esc to cancel
          </span>
          <span className="pref-editspace" />
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            type="submit"
            disabled={!text.trim() || (!adding && !changed)}
            aria-keyshortcuts="Enter"
          >
            Save
          </Button>
        </div>
      </form>
    </li>
  );
}
