import type { ReactNode } from "react";

interface PageHeaderProps {
  actions?: ReactNode;
  chips?: ReactNode;
  description: string;
  title: string;
}

export function PageHeader({ actions, chips, description, title }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-xl font-semibold text-zinc-950">{title}</h2>
        <p className="mt-1 text-sm text-zinc-500">{description}</p>
      </div>
      {chips ? <div className="flex flex-wrap gap-2">{chips}</div> : null}
      {actions ? <div className="flex flex-wrap items-end gap-2">{actions}</div> : null}
    </div>
  );
}
