import {
  cloneElement,
  isValidElement,
  useId,
  type ReactElement,
  type ReactNode,
} from "react";
import { cx } from "./classes";

/**
 * A labelled control with an optional hint. A single input, select or
 * textarea child is tied to the label and the hint; any other content keeps
 * its own labelling.
 */
export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  const id = useId();
  const control =
    isValidElement(children) &&
    typeof children.type === "string" &&
    ["input", "textarea", "select"].includes(children.type);
  const child = control
    ? cloneElement(children as ReactElement<Record<string, unknown>>, {
        id,
        "aria-describedby": hint ? id + "-hint" : undefined,
      })
    : children;
  return (
    <div className={cx("field", className)}>
      <label className="field-label" htmlFor={control ? id : undefined}>
        {label}
      </label>
      {child}
      {hint && (
        <small className="hint" id={id + "-hint"}>
          {hint}
        </small>
      )}
    </div>
  );
}

/**
 * An on/off switch. `label` is its accessible name; pass `children` to show a
 * visible label beside it.
 */
export function Switch({
  label,
  checked,
  onChange,
  disabled = false,
  children,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
  children?: ReactNode;
}) {
  const control = (
    <input
      type="checkbox"
      role="switch"
      className="switch"
      aria-label={children ? undefined : label}
      checked={checked}
      disabled={disabled}
      onChange={(event) => onChange(event.target.checked)}
    />
  );
  return children ? (
    <label className="toggle">
      {control}
      <span>{children}</span>
    </label>
  ) : (
    control
  );
}
