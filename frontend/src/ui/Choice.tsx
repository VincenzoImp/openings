import { useId, type ReactNode } from "react";
import { cx } from "./cx";
import "./choice.css";

export interface ChoiceOption<T extends string> {
  value: T;
  label: ReactNode;
  hint?: ReactNode;
  disabled?: boolean;
}

/**
 * One choice among a few, as native radio buttons in a fieldset: the legend
 * above (13/500), one 36 px row per option with an optional hint. Arrow keys
 * move between the options, as the browser does.
 */
export function Choice<T extends string>({
  legend,
  options,
  value,
  onChange,
  name,
  className,
}: {
  legend: ReactNode;
  options: ChoiceOption<T>[];
  value: T | null;
  onChange: (value: T) => void;
  name?: string;
  className?: string;
}) {
  const id = useId();
  return (
    <fieldset className={cx("ui-choice", className)}>
      <legend className="ui-field-label">{legend}</legend>
      {options.map((option) => (
        <label
          key={option.value}
          className="ui-choice-option"
          data-disabled={option.disabled || undefined}
        >
          <input
            type="radio"
            className="ui-radio"
            name={name ?? id}
            value={option.value}
            checked={value === option.value}
            disabled={option.disabled}
            onChange={() => onChange(option.value)}
          />
          <span className="ui-choice-text">
            <span>{option.label}</span>
            {option.hint && <span className="ui-field-hint">{option.hint}</span>}
          </span>
        </label>
      ))}
    </fieldset>
  );
}
