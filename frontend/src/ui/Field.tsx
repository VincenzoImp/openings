import {
  createContext,
  forwardRef,
  useContext,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { ChevronDown, CircleAlert, Search } from "lucide-react";
import { Kbd } from "./Button";
import { cx } from "./cx";
import { Icon } from "./Icon";
import "./field.css";

interface FieldWiring {
  id: string;
  describedBy?: string;
  invalid: boolean;
  required?: boolean;
}
const FieldContext = createContext<FieldWiring | null>(null);

/** The id, description and validity a control takes from its Field. */
function useField(id?: string) {
  const field = useContext(FieldContext);
  return {
    id: id ?? field?.id,
    "aria-describedby": field?.describedBy,
    "aria-invalid": field?.invalid || undefined,
    required: field?.required,
  };
}

/**
 * A labelled control: label above (13/500), hint below in text-3, and the
 * error below in danger with an icon, replacing the hint. The control inside
 * (Input, Select, Textarea) is wired to the label, hint and error.
 */
export function Field({
  label,
  hint,
  error,
  required,
  optional,
  className,
  children,
}: {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  /** Shows "Optional" beside the label. */
  optional?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const id = useId();
  const note = `${id}-note`;
  return (
    <FieldContext.Provider
      value={{
        id,
        describedBy: error || hint ? note : undefined,
        invalid: Boolean(error),
        required,
      }}
    >
      <div className={cx("ui-field", className)}>
        <label className="ui-field-label" htmlFor={id}>
          {label}
          {optional && <span className="ui-field-optional">Optional</span>}
        </label>
        {children}
        {error ? (
          <p className="ui-field-error" id={note}>
            <Icon icon={CircleAlert} size="sm" />
            <span>{error}</span>
          </p>
        ) : (
          hint && (
            <p className="ui-field-hint" id={note}>
              {hint}
            </p>
          )
        )}
      </div>
    </FieldContext.Provider>
  );
}

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(function Input({ className, id, ...rest }, ref) {
  return (
    <input
      ref={ref}
      className={cx("ui-input", className)}
      {...useField(id)}
      {...rest}
    />
  );
});

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, id, rows = 4, ...rest }, ref) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      className={cx("ui-input ui-textarea", className)}
      {...useField(id)}
      {...rest}
    />
  );
});

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className, id, children, ...rest }, ref) {
  return (
    <span className={cx("ui-select", className)}>
      <select ref={ref} className="ui-input" {...useField(id)} {...rest}>
        {children}
      </select>
      <Icon icon={ChevronDown} size="sm" className="ui-select-chevron" />
    </span>
  );
});

type Toggle = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label: ReactNode;
  hint?: ReactNode;
};

/** A checkbox with its label on the right. */
export const Checkbox = forwardRef<HTMLInputElement, Toggle>(
  function Checkbox({ label, hint, className, ...rest }, ref) {
    const id = useId();
    return (
      <label className={cx("ui-toggle", className)}>
        <input
          ref={ref}
          type="checkbox"
          className="ui-checkbox"
          aria-describedby={hint ? `${id}-hint` : undefined}
          {...rest}
        />
        <span className="ui-toggle-text">
          <span>{label}</span>
          {hint && (
            <span className="ui-field-hint" id={`${id}-hint`}>
              {hint}
            </span>
          )}
        </span>
      </label>
    );
  },
);

/** An on/off setting that applies at once, as a switch. */
export const Switch = forwardRef<HTMLInputElement, Toggle>(function Switch(
  { label, hint, className, ...rest },
  ref,
) {
  const id = useId();
  return (
    <label className={cx("ui-toggle", className)}>
      <input
        ref={ref}
        type="checkbox"
        role="switch"
        className="ui-switch"
        aria-describedby={hint ? `${id}-hint` : undefined}
        {...rest}
      />
      <span className="ui-toggle-text">
        <span>{label}</span>
        {hint && (
          <span className="ui-field-hint" id={`${id}-hint`}>
            {hint}
          </span>
        )}
      </span>
    </label>
  );
});

/** The search field of a toolbar or the sidebar, with its shortcut. */
export const SearchField = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement> & { label: string; shortcut?: string }
>(function SearchField({ label, shortcut, className, ...rest }, ref) {
  return (
    <span className={cx("ui-search", className)}>
      <Icon icon={Search} className="ui-search-icon" />
      <input
        ref={ref}
        type="search"
        aria-label={label}
        placeholder={label}
        aria-keyshortcuts={shortcut}
        {...rest}
      />
      {shortcut && <Kbd>{shortcut}</Kbd>}
    </span>
  );
});
