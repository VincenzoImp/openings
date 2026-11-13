import type { ReactNode } from "react";
import { IconButton } from "./Button";
import { cx } from "./classes";

/** An ordered list of short statements, such as those of Preferences. */
export function StatementList({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <ul className="list statements" aria-label={label}>
      {children}
    </ul>
  );
}

/**
 * One statement: a label with its tags, the text, and the actions at the end.
 * `onUp` and `onDown` reorder it from the keyboard; leave one out at the end
 * of the list. With `editing`, the children are the form that edits it.
 */
export function Statement({
  name,
  label,
  tags,
  caption,
  actions,
  editing = false,
  onUp,
  onDown,
  movable = true,
  disabled = false,
  children,
}: {
  /** The statement's name inside the labels of its controls. */
  name: string;
  label?: ReactNode;
  tags?: ReactNode;
  caption?: ReactNode;
  actions?: ReactNode;
  editing?: boolean;
  onUp?: () => void;
  onDown?: () => void;
  /** False for a list that has no order to change, or a statement being added. */
  movable?: boolean;
  disabled?: boolean;
  children?: ReactNode;
}) {
  return (
    <li className={cx(editing && "editing")}>
      {movable && (
        <span className="handle">
          <IconButton
            icon="up"
            label={`Move ${name} up`}
            data-dirty-control="true"
            disabled={disabled || !onUp}
            onClick={onUp}
          />
          <IconButton
            icon="down"
            label={`Move ${name} down`}
            data-dirty-control="true"
            disabled={disabled || !onDown}
            onClick={onDown}
          />
        </span>
      )}
      {editing ? (
        children
      ) : (
        <>
          <div className="grow">
            {(label || tags) && (
              <div className="label">
                {label}
                {tags}
              </div>
            )}
            {children}
            {caption && <div className="caption">{caption}</div>}
          </div>
          {actions && <div className="item-actions">{actions}</div>}
        </>
      )}
    </li>
  );
}

/** The value of a statement, shown as a small chip under its text. */
export function StatementValue({ children }: { children: ReactNode }) {
  return <span className="value">{children}</span>;
}
