import type { ButtonHTMLAttributes, Ref } from "react";
import { Icon, type IconName } from "./Icon";
import { buttonClass } from "./classes";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  ref?: Ref<HTMLButtonElement>;
  /** "primary", "quiet" or "danger"; empty for the default button. */
  variant?: string;
  size?: "sm" | "md";
  icon?: IconName;
  /** Shows a spinner and refuses clicks while an action runs. */
  loading?: boolean;
};

export function Button({
  children,
  variant = "",
  size,
  icon,
  loading = false,
  className,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      className={buttonClass(variant, size, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
    >
      {loading ? (
        <span className="spinner" aria-hidden="true" />
      ) : (
        icon && <Icon name={icon} />
      )}
      {children}
    </button>
  );
}

/** A button that shows only an icon; `label` is its accessible name. */
export function IconButton({
  icon,
  label,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  icon: IconName;
  label: string;
}) {
  return (
    <button
      type="button"
      {...props}
      className={buttonClass("", "", className, true)}
      aria-label={label}
      title={label}
    >
      <Icon name={icon} />
    </button>
  );
}
