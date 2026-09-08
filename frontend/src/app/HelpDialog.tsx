import { Dialog } from "../components/Dialog";
import { Kbd } from "../components/Kbd";
import { useShortcutList } from "./hotkeys";

const ORDER = ["Everywhere", "Lists", "Pipeline", "Job page"];

/** Generated from the hotkeys currently registered, so it never drifts. */
export function HelpDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const shortcuts = useShortcutList();
  const groups = new Map<string, { label: string; description: string }[]>();
  for (const item of shortcuts) {
    const list = groups.get(item.group) ?? [];
    list.push(item);
    groups.set(item.group, list);
  }
  const ordered = Array.from(groups.entries()).sort(
    ([a], [b]) =>
      (ORDER.indexOf(a) === -1 ? 99 : ORDER.indexOf(a)) -
      (ORDER.indexOf(b) === -1 ? 99 : ORDER.indexOf(b)),
  );

  return (
    <Dialog open={open} title="Keyboard shortcuts" onClose={onClose} wide>
      <div className="grid gap-4 sm:grid-cols-2">
        {ordered.map(([group, items]) => (
          <div key={group}>
            <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-fg-muted">
              {group}
            </h3>
            <dl className="flex flex-col gap-1">
              {items.map((item) => (
                <div key={item.label} className="flex items-start gap-2 text-sm">
                  <dt className="w-20 shrink-0">
                    <Kbd>{item.label}</Kbd>
                  </dt>
                  <dd className="text-fg-muted">{item.description}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
        <div className="text-sm text-fg-muted">
          <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-fg-muted">
            Dialogs
          </h3>
          <div className="flex items-start gap-2">
            <dt className="w-20 shrink-0">
              <Kbd>Esc</Kbd>
            </dt>
            <dd>Close the dialog</dd>
          </div>
        </div>
      </div>
    </Dialog>
  );
}
