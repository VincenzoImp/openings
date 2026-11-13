import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cx } from "./cx";
import { Icon, type LucideIcon } from "./Icon";
import "./button.css";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

/** A keyboard key or shortcut hint: <Kbd>⌘K</Kbd>. */
export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="ui-kbd">{children}</kbd>;
}

type NativeButton = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children">;

/**
 * A text button. Primary is the one filled button of a pane; secondary is an
 * alternative; ghost is for Cancel, Edit and toolbar actions. Danger is only
 * the confirm of a permanent deletion (in menus, use a danger menu item).
 */
export const Button = forwardRef<
  HTMLButtonElement,
  NativeButton & {
    variant?: ButtonVariant;
    size?: "md" | "sm" | "touch";
    icon?: LucideIcon;
    kbd?: string;
    children: ReactNode;
  }
>(function Button(
  {
    variant = "secondary",
    size = "md",
    icon,
    kbd,
    className,
    type = "button",
    children,
    ...rest
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cx("ui-btn", className)}
      data-variant={variant}
      data-size={size === "md" ? undefined : size}
      {...rest}
    >
      {icon && <Icon icon={icon} />}
      <span className="ui-btn-label">{children}</span>
      {kbd && <Kbd>{kbd}</Kbd>}
    </button>
  );
});

/**
 * An icon-only button: ghost style, an accessible name, and a tooltip that
 * names the action and its shortcut. `raised` is the small square of a row's
 * hover actions.
 */
export const IconButton = forwardRef<
  HTMLButtonElement,
  NativeButton & {
    icon: LucideIcon;
    label: string;
    shortcut?: string;
    size?: "md" | "sm" | "touch";
    raised?: boolean;
    tooltip?: "below" | "above" | "none";
  }
>(function IconButton(
  {
    icon,
    label,
    shortcut,
    size = "md",
    raised = false,
    tooltip = "below",
    className,
    type = "button",
    ...rest
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cx("ui-btn ui-icon-btn", className)}
      data-variant={raised ? "raised" : "ghost"}
      data-size={size === "md" ? undefined : size}
      aria-label={label}
      aria-keyshortcuts={shortcut}
      data-tip={tooltip === "none" ? undefined : tooltip}
      data-tip-text={shortcut ? `${label}  ${shortcut}` : label}
      {...rest}
    >
      <Icon
        icon={icon}
        size={size === "touch" ? "lg" : size === "sm" ? "sm" : "md"}
      />
    </button>
  );
});
