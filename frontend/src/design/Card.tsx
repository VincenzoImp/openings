import { useId, type ReactNode, type Ref } from "react";
import { cx } from "./classes";
import { Count } from "./Tag";

/** A titled group. Content is a list, a `.body` block or both. */
export function Card({
  title,
  count,
  actions,
  footer,
  className,
  ref,
  children,
}: {
  title?: string;
  ref?: Ref<HTMLElement>;
  count?: number;
  /** Controls at the end of the header. */
  actions?: ReactNode;
  footer?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <section
      ref={ref}
      className={cx("card", className)}
      aria-labelledby={title ? id : undefined}
    >
      {title && (
        <header>
          <h2 id={id} className="grow">
            {title}
          </h2>
          {count !== undefined && <Count value={count} />}
          {actions}
        </header>
      )}
      {children}
      {footer && <footer>{footer}</footer>}
    </section>
  );
}

export function CardBody({ children }: { children: ReactNode }) {
  return <div className="body stack">{children}</div>;
}

export function List({
  label,
  children,
}: {
  label?: string;
  children: ReactNode;
}) {
  return (
    <ul className="list" aria-label={label}>
      {children}
    </ul>
  );
}

/** One row: a title (link, button or text), a line of detail and trailing items. */
export function ListRow({
  title,
  meta,
  href,
  onOpen,
  selected = false,
  foot,
  children,
}: {
  title: ReactNode;
  meta?: ReactNode;
  /** A last line under the detail, such as who did it. */
  foot?: ReactNode;
  href?: string;
  onOpen?: () => void;
  selected?: boolean;
  /** Tags and actions after the text. */
  children?: ReactNode;
}) {
  return (
    <li
      className={selected ? "is-selected" : undefined}
      aria-current={selected || undefined}
    >
      <div className="grow">
        {href ? (
          <a className="title" href={href}>
            {title}
          </a>
        ) : onOpen ? (
          <button type="button" className="title" onClick={onOpen}>
            {title}
          </button>
        ) : (
          <span className="title">{title}</span>
        )}
        {meta && <div className="meta">{meta}</div>}
        {foot}
      </div>
      {children}
    </li>
  );
}
