import type { ReactNode } from "react";

export interface ChipOption {
  id: string;
  label: string;
  count?: number;
}

/** Filter chips: one choice of a small set, each a pressed or unpressed button. */
export function Chips({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: ChipOption[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="chips" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          type="button"
          className="chip"
          key={option.id}
          aria-pressed={option.id === value}
          onClick={() => onChange(option.id)}
        >
          {option.label}
          {option.count !== undefined && (
            <span className="num">{option.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}

/** Filters above a list: chips, selects and date fields in one wrapping row. */
export function FilterBar({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="filterbar" role="group" aria-label={label}>
      {children}
    </div>
  );
}
