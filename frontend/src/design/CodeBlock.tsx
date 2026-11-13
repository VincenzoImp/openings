import { IconButton } from "./Button";
import { cx } from "./classes";

/**
 * Text to paste somewhere else, such as a command or a configuration file,
 * with a copy button inside the block. Long lines wrap, so nothing is hidden
 * past the edge on a narrow screen; `inline` fits one short value in a line.
 */
export function CodeBlock({
  children,
  label,
  copyLabel,
  onCopy,
  inline = false,
}: {
  children: string;
  /** The accessible name of the text: "MCP configuration". */
  label: string;
  /** The accessible name of the button: "Copy the MCP configuration". */
  copyLabel: string;
  onCopy: () => void;
  inline?: boolean;
}) {
  return (
    <div className={cx("code-block", inline && "inline")}>
      <pre className="code wrap" tabIndex={0} aria-label={label}>
        {children}
      </pre>
      <IconButton icon="copy" label={copyLabel} onClick={onCopy} />
    </div>
  );
}
