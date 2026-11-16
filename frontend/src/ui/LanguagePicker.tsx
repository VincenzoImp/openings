import { useState, type ReactNode } from "react";
import { Button } from "./Button";
import { Field, Input, Select } from "./Field";
import { Chip } from "./Tabs";
import { LANGUAGES, languageCode, languageName } from "./languages";
import "./languages.css";

/**
 * The languages someone speaks, shared by Setup and Preferences: a removable
 * chip for each, the same list to add from, and "Other language…" for any
 * other, by its English name or its ISO 639-1 code; the hint names the
 * language it reads.
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
  const code = other ? languageCode(other) : null;
  const add = (code: string) => {
    if (!value.includes(code)) onChange([...value, code]);
    setOther(null);
  };
  return (
    <div className="ui-lang-picker">
      {value.length > 0 && (
        <ul className="ui-lang-chips">
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
        <div className="ui-lang-add">
          <Select
            aria-label="Add a language"
            value=""
            disabled={disabled}
            onChange={(event) =>
              event.target.value === "other"
                ? setOther("")
                : event.target.value && add(event.target.value)
            }
          >
            <option value="">Add a language…</option>
            {LANGUAGES.filter(([code]) => !value.includes(code)).map(
              ([code, name]) => (
                <option key={code} value={code}>
                  {name}
                </option>
              ),
            )}
            <option value="other">Other language…</option>
          </Select>
          {children}
        </div>
      ) : (
        <div className="ui-lang-other">
          <Field
            label="Other language"
            hint={
              code
                ? `Adds ${languageName(code)}.`
                : "Its English name or ISO code, such as Yoruba or yo."
            }
          >
            <Input
              value={other}
              maxLength={60}
              autoFocus
              autoComplete="off"
              onChange={(event) => setOther(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== "Enter") return;
                event.preventDefault();
                if (code) add(code);
              }}
            />
          </Field>
          <div className="ui-lang-add">
            <Button
              size="sm"
              disabled={disabled || !code}
              onClick={() => code && add(code)}
            >
              Add
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setOther(null)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
