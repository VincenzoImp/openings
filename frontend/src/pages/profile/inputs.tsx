// The entry form's composite controls: dates as month and year, skill tags,
// and the files of an entry.
import { useId, useRef, useState } from "react";
import { FileText, Plus, X } from "lucide-react";
import { Checkbox, Input, Select } from "../../ui/Field";
import { Icon } from "../../ui/Icon";
import { fileSize, type EntryFile } from "./data";
import { MONTH_NAMES, addSkills, type DateDraft } from "./model";

function MonthYear({
  label,
  month,
  year,
  disabled,
  onMonth,
  onYear,
}: {
  label: string;
  month: string;
  year: string;
  disabled?: boolean;
  onMonth: (value: string) => void;
  onYear: (value: string) => void;
}) {
  const id = useId();
  return (
    <div className="pf-date" role="group" aria-labelledby={id}>
      <span className="ui-field-label" id={id}>
        {label}
      </span>
      <div className="pf-date-controls">
        <Select
          aria-label={`${label} month`}
          value={month}
          disabled={disabled}
          onChange={(event) => onMonth(event.target.value)}
        >
          <option value="">Month</option>
          {MONTH_NAMES.map((name, index) => (
            <option key={name} value={String(index + 1).padStart(2, "0")}>
              {name}
            </option>
          ))}
        </Select>
        <Input
          aria-label={`${label} year`}
          inputMode="numeric"
          placeholder="Year"
          maxLength={4}
          value={year}
          disabled={disabled}
          onChange={(event) => onYear(event.target.value.replace(/\D/g, ""))}
        />
      </div>
    </div>
  );
}

/** Start, end and Present; a start alone is one date. */
export function DatesInput({
  value,
  error,
  onChange,
}: {
  value: DateDraft;
  error?: string;
  onChange: (value: DateDraft) => void;
}) {
  const id = useId();
  return (
    <fieldset className="pf-dates" aria-describedby={error ? id : undefined}>
      <legend className="ui-field-label">Dates</legend>
      <div className="pf-dates-row">
        <MonthYear
          label="Start"
          month={value.startMonth}
          year={value.startYear}
          onMonth={(startMonth) => onChange({ ...value, startMonth })}
          onYear={(startYear) => onChange({ ...value, startYear })}
        />
        <MonthYear
          label="End"
          month={value.current ? "" : value.endMonth}
          year={value.current ? "" : value.endYear}
          disabled={value.current}
          onMonth={(endMonth) => onChange({ ...value, endMonth })}
          onYear={(endYear) => onChange({ ...value, endYear })}
        />
        <Checkbox
          className="pf-present"
          label="Present"
          checked={value.current}
          onChange={(event) =>
            onChange({ ...value, current: event.target.checked })
          }
        />
      </div>
      {error && (
        <p className="ui-field-error" id={id}>
          {error}
        </p>
      )}
    </fieldset>
  );
}

/** Skill tags: Enter or a comma adds one; × or Backspace removes. */
export function SkillsInput({
  value,
  onChange,
}: {
  value: string[];
  onChange: (value: string[]) => void;
}) {
  const [text, setText] = useState("");
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const add = (typed: string) => {
    const next = addSkills(value, typed);
    if (next.length !== value.length) onChange(next);
    setText("");
  };
  return (
    <div className="ui-field">
      <label className="ui-field-label" htmlFor={id}>
        Skills
      </label>
      <div className="pf-skills-input" onClick={() => input.current?.focus()}>
        {value.map((skill) => (
          <span className="ui-tag pf-skill" key={skill}>
            {skill}
            <button
              type="button"
              aria-label={`Remove ${skill}`}
              onClick={() => onChange(value.filter((item) => item !== skill))}
            >
              <Icon icon={X} size="sm" />
            </button>
          </span>
        ))}
        <input
          ref={input}
          id={id}
          value={text}
          placeholder={value.length ? "" : "Python, SQL…"}
          onChange={(event) =>
            event.target.value.includes(",")
              ? add(event.target.value)
              : setText(event.target.value)
          }
          onBlur={() => text.trim() && add(text)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.metaKey && !event.ctrlKey) {
              event.preventDefault();
              add(text);
            } else if (event.key === "Backspace" && !text && value.length)
              onChange(value.slice(0, -1));
          }}
        />
      </div>
    </div>
  );
}

export interface FilesDraft {
  removed: string[];
  added: File[];
}

/** The files of an entry: kept, to remove, and to add on Save. */
export function FilesInput({
  stored,
  value,
  onChange,
}: {
  stored: EntryFile[];
  value: FilesDraft;
  onChange: (value: FilesDraft) => void;
}) {
  const id = useId();
  const kept = stored.filter((file) => !value.removed.includes(file.id));
  return (
    <fieldset className="pf-files-edit">
      <legend className="ui-field-label">Files</legend>
      {(kept.length > 0 || value.added.length > 0) && (
        <ul className="pf-files">
          {kept.map((file) => (
            <li className="pf-file" key={file.id}>
              <Icon icon={FileText} size="sm" />
              <span className="pf-file-name">{file.name}</span>
              <span className="pf-file-size">{fileSize(file.size)}</span>
              <button
                type="button"
                aria-label={`Remove ${file.name}`}
                onClick={() =>
                  onChange({ ...value, removed: [...value.removed, file.id] })
                }
              >
                <Icon icon={X} size="sm" />
              </button>
            </li>
          ))}
          {value.added.map((file, index) => (
            <li className="pf-file" data-new="" key={`new-${index}`}>
              <Icon icon={FileText} size="sm" />
              <span className="pf-file-name">{file.name}</span>
              <span className="pf-file-size">{fileSize(file.size)}</span>
              <button
                type="button"
                aria-label={`Remove ${file.name}`}
                onClick={() =>
                  onChange({
                    ...value,
                    added: value.added.filter((_, at) => at !== index),
                  })
                }
              >
                <Icon icon={X} size="sm" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <label className="ui-btn pf-file-add" data-variant="ghost" data-size="sm">
        <Icon icon={Plus} />
        <span className="ui-btn-label">Attach a file</span>
        <input
          id={id}
          type="file"
          multiple
          className="pf-visually-hidden"
          onChange={(event) => {
            const files = [...(event.target.files ?? [])];
            event.target.value = "";
            if (files.length)
              onChange({ ...value, added: [...value.added, ...files] });
          }}
        />
      </label>
    </fieldset>
  );
}
