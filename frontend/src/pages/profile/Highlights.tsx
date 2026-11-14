// Highlights: the CV bullets of an entry. At rest, bullets with ★ (always
// include in my CV) and, for one not approved yet, "Not approved" and
// Approve. In the entry's form: add, reword, approve, star, remove and
// reorder (drag the handle, or its menu: Move up / Move down).
import { useLayoutEffect, useRef, useState } from "react";
import { Check, Menu as Grip, Plus, Star, Trash } from "lucide-react";
import { Button, IconButton } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import { Menu } from "../../ui/Menu";
import { useToast } from "../../ui/Toast";
import { useApiMutation } from "../../query/mutation";
import { writes, type Highlight } from "./data";

/** The bullets of an entry, read. */
export function HighlightList({ items }: { items: Highlight[] }) {
  if (!items.length) return null;
  return (
    <ul className="pf-highlights" aria-label="Highlights">
      {items.map((item) => (
        <li key={item.id} data-unapproved={!item.approved || undefined}>
          <span className="pf-hl-text">{item.text ?? item.text_preview}</span>
          {item.always_include && (
            <span
              className="pf-star-mark"
              role="img"
              aria-label="Always include in my CV"
              title="Always include in my CV"
            >
              <Icon icon={Star} size="sm" />
            </span>
          )}
          {!item.approved && <Approve item={item} />}
        </li>
      ))}
    </ul>
  );
}

function Approve({ item }: { item: Highlight }) {
  const toast = useToast();
  const approve = useApiMutation({
    touches: ["career"],
    mutationFn: () =>
      writes.updateHighlight(item.id, {
        expected_version: item.version,
        approved: true,
      }),
    onSuccess: () =>
      toast.show({ message: "Approved the highlight", tone: "success" }),
    onError: (error) => toast.show({ message: error.message, tone: "error" }),
  });
  return (
    <span className="pf-pending">
      Not approved
      <Button
        size="sm"
        disabled={approve.isPending}
        aria-label={`Approve: ${item.text ?? item.text_preview}`}
        onClick={() => approve.mutate()}
      >
        Approve
      </Button>
    </span>
  );
}

export interface HighlightDraft {
  /** A stable key in the form; the id once stored. */
  key: string;
  id?: string;
  text: string;
  approved: boolean;
  always: boolean;
}

export const draftOf = (item: Highlight): HighlightDraft => ({
  key: item.id,
  id: item.id,
  text: item.text ?? "",
  approved: item.approved,
  always: item.always_include,
});

let counter = 0;
const newKey = () => `new-${++counter}`;

/** Grow a textarea with its text. */
function AutoText(props: {
  value: string;
  label: string;
  onChange: (value: string) => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight + 2}px`;
  }, [props.value]);
  return (
    <textarea
      ref={ref}
      rows={1}
      className="ui-input ui-textarea pf-hl-input"
      aria-label={props.label}
      placeholder="What you did and what came of it"
      value={props.value}
      maxLength={5000}
      onChange={(event) => props.onChange(event.target.value)}
    />
  );
}

export function HighlightsEditor({
  value,
  onChange,
}: {
  value: HighlightDraft[];
  onChange: (value: HighlightDraft[]) => void;
}) {
  const [dragging, setDragging] = useState<string | null>(null);
  const [armed, setArmed] = useState<string | null>(null);
  const list = useRef<HTMLOListElement>(null);
  const patch = (key: string, change: Partial<HighlightDraft>) =>
    onChange(
      value.map((item) => (item.key === key ? { ...item, ...change } : item)),
    );
  const move = (from: number, to: number) => {
    if (to < 0 || to >= value.length || from === to) return;
    const next = [...value];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    onChange(next);
  };
  const add = () => {
    const key = newKey();
    onChange([...value, { key, text: "", approved: true, always: false }]);
    requestAnimationFrame(() =>
      list.current
        ?.querySelector<HTMLTextAreaElement>(`[data-key="${key}"] textarea`)
        ?.focus(),
    );
  };
  return (
    <fieldset className="pf-hl-edit">
      <legend className="ui-field-label">Highlights</legend>
      {value.length > 0 && (
        <ol className="pf-hl-rows" ref={list}>
          {value.map((item, index) => (
            <li
              key={item.key}
              data-key={item.key}
              data-unapproved={!item.approved || undefined}
              data-dragging={dragging === item.key || undefined}
              draggable={armed === item.key}
              onDragStart={(event) => {
                event.dataTransfer.effectAllowed = "move";
                event.dataTransfer.setData("text/plain", item.key);
                setDragging(item.key);
              }}
              onDragOver={(event) => {
                if (!dragging) return;
                event.preventDefault();
                const from = value.findIndex((row) => row.key === dragging);
                if (from !== index) move(from, index);
              }}
              onDrop={(event) => event.preventDefault()}
              onDragEnd={() => {
                setDragging(null);
                setArmed(null);
              }}
            >
              <Menu
                label={`Move highlight ${index + 1}`}
                items={[
                  {
                    id: "up",
                    label: "Move up",
                    disabled: index === 0,
                    onSelect: () => move(index, index - 1),
                  },
                  {
                    id: "down",
                    label: "Move down",
                    disabled: index === value.length - 1,
                    onSelect: () => move(index, index + 1),
                  },
                ]}
                trigger={(props) => (
                  <button
                    {...props}
                    type="button"
                    className="pf-hl-handle"
                    aria-label={`Move highlight ${index + 1}`}
                    onPointerDown={() => setArmed(item.key)}
                    onPointerUp={() => setArmed(null)}
                  >
                    <Icon icon={Grip} size="sm" />
                  </button>
                )}
              />
              <AutoText
                label={`Highlight ${index + 1}`}
                value={item.text}
                onChange={(text) => patch(item.key, { text })}
              />
              <div className="pf-hl-tools">
                {item.approved ? (
                  <span className="pf-hl-ok" title="Approved">
                    <Icon icon={Check} size="sm" />
                    <span className="pf-visually-hidden">Approved</span>
                  </span>
                ) : (
                  <Button
                    size="sm"
                    variant="secondary"
                    aria-label={`Approve highlight ${index + 1}`}
                    onClick={() => patch(item.key, { approved: true })}
                  >
                    Approve
                  </Button>
                )}
                <IconButton
                  icon={Star}
                  size="sm"
                  className="pf-star"
                  label="Always include in my CV"
                  aria-pressed={item.always}
                  tooltip="above"
                  onClick={() => patch(item.key, { always: !item.always })}
                />
                <IconButton
                  icon={Trash}
                  size="sm"
                  label={`Remove highlight ${index + 1}`}
                  tooltip="above"
                  onClick={() =>
                    onChange(value.filter((row) => row.key !== item.key))
                  }
                />
              </div>
            </li>
          ))}
        </ol>
      )}
      <Button variant="ghost" size="sm" icon={Plus} onClick={add}>
        Add highlight
      </Button>
    </fieldset>
  );
}
