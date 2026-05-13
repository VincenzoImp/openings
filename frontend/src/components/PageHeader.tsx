import type { ReactNode } from "react";

interface PageHeaderProps {
  actions?: ReactNode;
  chips?: ReactNode;
  description: string;
  title: string;
}

export function PageHeader({ actions, chips, description, title }: PageHeaderProps) {
  return (
    <div className="grid min-w-0 gap-3 sm:flex sm:flex-wrap sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h2 className="text-xl font-semibold text-zinc-950">{title}</h2>
        <p className="mt-1 text-sm text-zinc-500">{description}</p>
      </div>
      {chips ? <div className="flex min-w-0 flex-wrap gap-2">{chips}</div> : null}
      {actions ? <div className="flex min-w-0 flex-wrap items-end gap-2">{actions}</div> : null}
    </div>
  );
}
