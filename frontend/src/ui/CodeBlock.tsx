import { Copy } from "lucide-react";
import { IconButton } from "./Button";
import { cx } from "./cx";
import "./codeblock.css";

/** Copy text to the clipboard; false when the browser refuses. */
export async function copyText(value: string) {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    // Older browsers and some embedded views: a hidden field and execCommand.
    const field = document.createElement("textarea");
    field.value = value;
    field.setAttribute("readonly", "");
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.append(field);
    field.select();
    const done = document.execCommand?.("copy") ?? false;
    field.remove();
    return done;
  }
}

/**
 * A command or configuration in monospace, wrapped so nothing hides past the
 * edge, with its copy button inside, top right. `inline` is one short value
 * (an address).
 */
export function CodeBlock({
  code,
  label,
  inline = false,
  onCopied,
  className,
}: {
  code: string;
  /** The accessible name of the block; the button reads "Copy <label>". */
  label: string;
  inline?: boolean;
  /** Told whether the copy worked, for a toast. */
  onCopied?: (ok: boolean) => void;
  className?: string;
}) {
  return (
    <div className={cx("ui-code", className)} data-inline={inline || undefined}>
      <pre role="region" aria-label={label} tabIndex={0}>
        <code>{code}</code>
      </pre>
      <IconButton
        icon={Copy}
        label={`Copy ${label.toLowerCase()}`}
        size="sm"
        tooltip="above"
        className="ui-code-copy"
        onClick={async () => {
          const ok = await copyText(code);
          onCopied?.(ok);
        }}
      />
    </div>
  );
}
