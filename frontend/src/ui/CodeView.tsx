import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cx } from "./cx";
import "./codeview.css";

const numbers = (text: string) =>
  Array.from({ length: Math.max(1, text.split("\n").length) }, (_, index) =>
    String(index + 1),
  ).join("\n");

/**
 * Source code to read (a LaTeX template): monospace, with line numbers, no
 * wrapping. It scrolls sideways on its own, so it is a focusable region.
 */
export function CodeView({
  code,
  label,
  className,
}: {
  code: string;
  label: string;
  className?: string;
}) {
  return (
    <div
      className={cx("ui-code", className)}
      role="region"
      aria-label={label}
      tabIndex={0}
    >
      <pre className="ui-code-gutter" aria-hidden="true">
        {numbers(code)}
      </pre>
      <pre className="ui-code-text">
        <code>{code}</code>
      </pre>
    </div>
  );
}

/**
 * Source code to edit: the same look as CodeView, with a plain text area
 * that grows with its lines (the pane scrolls, not the field).
 */
export const CodeEditor = forwardRef<
  HTMLTextAreaElement,
  Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "value"> & {
    value: string;
  }
>(function CodeEditor({ value, className, ...rest }, ref) {
  const lines = value.split("\n").length;
  return (
    <div className={cx("ui-code ui-code-edit", className)}>
      <pre className="ui-code-gutter" aria-hidden="true">
        {numbers(value)}
      </pre>
      <textarea
        ref={ref}
        className="ui-code-input"
        value={value}
        rows={Math.max(lines + 1, 12)}
        wrap="off"
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
        {...rest}
      />
    </div>
  );
});
