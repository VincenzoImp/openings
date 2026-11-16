import { useState, type KeyboardEvent, type ReactNode } from "react";
import { Button, Chip, Field, Input, Select } from "../../ui";
import { LANGUAGES, languageCode, languageName } from "../../ui/languages";
import "./languages.css";

const OTHER = "other";

/**
 * The languages someone speaks, shared by Setup and Preferences: a removable
 * chip for each, the same list to add from, and "Other language…" for any
 * other, by its name or its ISO 639-1 code.
 */
export function LanguagePicker({
  value,
  onChange,
  disabled,
  children,
}: {
  value: string[];
  onChange: (languages: string[]) => void;
  disabled?: boolean;
  /** Beside the list, such as Preferences' Done. */
  children?: ReactNode;
}) {
  const [other, setOther] = useState<string | null>(null);
  const [invalid, setInvalid] = useState(false);
  const offered = LANGUAGES.filter(([code]) => !value.includes(code));
  function addOther() {
    const code = languageCode(other ?? "");
    if (!code) return setInvalid(true);
    if (!value.includes(code)) onChange([...value, code]);
    setOther(null);
    setInvalid(false);
  }
  function onKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      addOther();
    } else if (event.key === "Escape") {
      event.stopPropagation();
      setOther(null);
      setInvalid(false);
    }
  }
  return (
    <div className="lang-picker">
      {value.length > 0 && (
        <ul className="lang-chips" aria-label="Languages you speak">
          {value.map((code) => (
            <li key={code}>
              <Chip
                removeLabel={`Remove ${languageName(code)}`}
                disabled={disabled}
                onRemove={() => onChange(value.filter((item) => item !== code))}
              >
                {languageName(code)}
              </Chip>
            </li>
          ))}
        </ul>
      )}
      {other == null ? (
        <div className="lang-add">
          <Select
            aria-label="Add a language"
            value=""
            disabled={disabled}
            onChange={(event) => {
              const code = event.target.value;
              if (code === OTHER) setOther("");
              else if (code) onChange([...value, code]);
            }}
          >
            <option value="">Add a language…</option>
            {offered.map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
            <option value={OTHER}>Other language…</option>
          </Select>
          {children}
        </div>
      ) : (
        <div className="lang-other">
          <Field
            label="Other language"
            hint="Its English name or its two-letter ISO code, such as Yoruba or yo."
            error={
              invalid
                ? "No language goes by that name or code; try its English name."
                : undefined
            }
          >
            <Input
              value={other}
              maxLength={60}
              autoFocus
              autoComplete="off"
              onChange={(event) => {
                setOther(event.target.value);
                setInvalid(false);
              }}
              onKeyDown={onKey}
            />
          </Field>
          <div className="lang-add">
            <Button
              size="sm"
              disabled={disabled || !other.trim()}
              onClick={addOther}
            >
              Add
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setOther(null);
                setInvalid(false);
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
