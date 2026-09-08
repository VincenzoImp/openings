import type { ReactNode } from "react";

export function Card({
  title,
  actions,
  children,
  className = "",
  padded = true,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <section className={`min-w-0 rounded-lg border border-edge bg-surface ${className}`}>
      {title !== undefined ? (
        <header className="flex items-center justify-between gap-2 border-b border-edge px-3 py-2">
          <h2 className="truncate text-[11px] font-semibold uppercase tracking-wide text-fg-muted">
            {title}
          </h2>
          {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
        </header>
      ) : null}
      <div className={padded ? "p-3 sm:p-4" : ""}>{children}</div>
    </section>
  );
}
