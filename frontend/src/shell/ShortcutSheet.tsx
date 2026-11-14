import { Button, Kbd } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { SHEET } from "./shortcuts";

/** `?`: every shortcut of the shell and of the lists. */
export function ShortcutSheet({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Keyboard shortcuts"
      footer={
        <Button variant="primary" onClick={onClose}>
          Done
        </Button>
      }
    >
      {SHEET.map((section) => (
        <section key={section.title} className="shell-keys">
          <h3>{section.title}</h3>
          <dl>
            {section.items.map(([keys, label]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>
                  {keys.map((key) => (
                    <Kbd key={key}>{key}</Kbd>
                  ))}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
    </Dialog>
  );
}
