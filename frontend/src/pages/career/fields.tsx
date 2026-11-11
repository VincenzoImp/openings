// Controls of the entry form: partial dates and skill tags.
import { useState } from "react";
import type { CareerDates } from "../../api";
import { Field, Tag } from "../../design";

export interface DateState {
  mode: "none" | CareerDates["kind"];
  start: { year: string; month: string };
  end: { year: string; month: string };
  current: boolean;
}
const parts = (value?: string | null) => {
  const [year = "", month = ""] = (value || "").split("-");
  return { year, month };
};
const joined = (value: { year: string; month: string }) =>
  value.year.padStart(4, "0") + (value.month ? `-${value.month}` : "");

export const dateState = (dates?: CareerDates | null): DateState => ({
  mode: dates?.kind || "none",
  start: parts(dates?.start),
  end: parts(dates?.end),
  current: dates?.current || false,
});
/** The dates to store: null, one date, or a period that ends or is current. */
export function datesOf(state: DateState): CareerDates | null {
  if (state.mode === "none") return null;
  const period = state.mode === "period";
  return {
    kind: state.mode,
    start: joined(state.start),
    end: period && !state.current ? joined(state.end) : null,
    current: period && state.current,
  };
}

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];
function DatePart({
  label,
  value,
  onChange,
}: {
  label: string;
  value: { year: string; month: string };
  onChange: (value: { year: string; month: string }) => void;
}) {
  return (
    <>
      <Field label={`${label} year`.trim()}>
        <input
          type="number"
          name={`${label || "date"}_year`.toLowerCase()}
          required
          min={1}
          max={9999}
          step={1}
          inputMode="numeric"
          placeholder="2025"
          value={value.year}
          onChange={(event) => onChange({ ...value, year: event.target.value })}
        />
      </Field>
      <Field label={`${label} month`.trim()}>
        <select
          name={`${label || "date"}_month`.toLowerCase()}
          value={value.month}
          onChange={(event) =>
            onChange({ ...value, month: event.target.value })
          }
        >
          <option value="">Year only</option>
          {MONTHS.map((name, index) => (
            <option key={name} value={String(index + 1).padStart(2, "0")}>
              {name}
            </option>
          ))}
        </select>
      </Field>
    </>
  );
}

/** No date, one date or a period; a year alone is a valid date. */
export function DateFields({
  value,
  onChange,
}: {
  value: DateState;
  onChange: (value: DateState) => void;
}) {
  return (
    <>
      <Field label="Dates" className="wide">
        <select
          name="date_mode"
          value={value.mode}
          onChange={(event) =>
            onChange({
              ...value,
              mode: event.target.value as DateState["mode"],
            })
          }
        >
          <option value="none">No date</option>
          <option value="single">One date</option>
          <option value="period">From and to</option>
        </select>
      </Field>
      {value.mode !== "none" && (
        <DatePart
          label={value.mode === "single" ? "" : "From"}
          value={value.start}
          onChange={(start) => onChange({ ...value, start })}
        />
      )}
      {value.mode === "period" && (
        <>
          <label className="toggle wide">
            <input
              name="current"
              type="checkbox"
              checked={value.current}
              onChange={(event) =>
                onChange({ ...value, current: event.target.checked })
              }
            />
            <span>Until today</span>
          </label>
          {!value.current && (
            <DatePart
              label="To"
              value={value.end}
              onChange={(end) => onChange({ ...value, end })}
            />
          )}
        </>
      )}
    </>
  );
}

/** Skill tags: Enter or a comma adds one, the × on a tag removes it. */
export function SkillsField({
  value,
  onChange,
}: {
  value: string[];
  onChange: (value: string[]) => void;
}) {
  const [text, setText] = useState("");
  const add = (raw: string) => {
    const next = [...value];
    for (const skill of raw.split(",").map((part) => part.trim()))
      if (
        skill &&
        !next.some((item) => item.toLowerCase() === skill.toLowerCase())
      )
        next.push(skill);
    if (next.length !== value.length) onChange(next);
    setText("");
  };
  return (
    <div className="field wide">
      <span className="field-label" id="skills-label">
        Skills
      </span>
      <div className="skill-edit" role="group" aria-labelledby="skills-label">
        {value.map((skill) => (
          <Tag key={skill}>
            {skill}
            <button
              type="button"
              aria-label={`Remove ${skill}`}
              data-dirty-control="true"
              onClick={() => onChange(value.filter((item) => item !== skill))}
            >
              ×
            </button>
          </Tag>
        ))}
        <input
          aria-label="Add a skill"
          placeholder="Add a skill"
          value={text}
          onChange={(event) =>
            event.target.value.includes(",")
              ? add(event.target.value)
              : setText(event.target.value)
          }
          onBlur={() => text.trim() && add(text)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              add(text);
            }
          }}
        />
      </div>
    </div>
  );
}
