import type { Source } from "../../api";
import { Field } from "../../design";
import {
  LIMITS,
  NATIONAL,
  PORTALS,
  type ConfigProperties,
  type SourceSchema,
} from "./model";

const JOB_TYPES = [
  "fulltime",
  "parttime",
  "contract",
  "temporary",
  "internship",
  "perdiem",
  "other",
  "volunteer",
];

/** The query, place and portals of a saved search. */
export function SearchFields({
  source,
  country,
  providers,
  onProviders,
}: {
  source?: Source;
  country: string;
  providers: string[];
  onProviders: (next: string[]) => void;
}) {
  const config = source?.config || {};
  return (
    <>
      <Field label="Keywords" hint="One query, sent to each portal you choose.">
        <input
          name="query"
          required
          maxLength={300}
          defaultValue={String(config.query || "")}
          placeholder="backend engineer"
        />
      </Field>
      <Field label="Location" hint="City, region or country.">
        <input
          name="location"
          defaultValue={String(config.location || "")}
          placeholder="Zurich, Switzerland"
        />
      </Field>
      <Field
        label="Country"
        hint="The portal's market, such as switzerland, uk or usa. Indeed and Glassdoor search one country's site and need it; LinkedIn uses the location alone."
      >
        <input
          name="country"
          required={providers.some((id) => NATIONAL.includes(id))}
          defaultValue={String(config.country || country)}
          placeholder={
            providers.some((id) => NATIONAL.includes(id))
              ? "switzerland"
              : "None"
          }
        />
      </Field>
      <fieldset className="field">
        <legend>Portals</legend>
        <div className="row">
          {PORTALS.map(([id, label]) => (
            <label className="toggle" key={id}>
              <input
                name="providers"
                type="checkbox"
                value={id}
                checked={providers.includes(id)}
                required={!providers.length && id === PORTALS[0][0]}
                onChange={(event) =>
                  onProviders(
                    event.target.checked
                      ? [...providers, id]
                      : providers.filter((value) => value !== id),
                  )
                }
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
    </>
  );
}

/** The address and service of a company board. */
export function BoardFields({
  source,
  kind,
  onKind,
  schemas,
  hasBoard,
}: {
  source?: Source;
  kind: string;
  onKind: (kind: string) => void;
  schemas: SourceSchema[];
  hasBoard: boolean;
}) {
  return (
    <>
      <Field
        label="Career page or feed address"
        hint="A supported applicant tracking board, or a public RSS or Atom feed."
        className="wide"
      >
        <input
          name="url"
          type="url"
          required
          defaultValue={source?.url || ""}
          placeholder="https://jobs.example.test/company"
        />
      </Field>
      <Field
        label="Board service"
        hint={
          source
            ? "The service is fixed; add another source for a different one."
            : "Detected from the address unless you choose one."
        }
      >
        <select
          value={kind}
          disabled={!!source}
          onChange={(event) => onKind(event.target.value)}
        >
          <option value="auto">Detect from the address</option>
          {schemas
            .filter((item) => !item.capabilities.search)
            .map((item) => (
              <option key={item.kind} value={item.kind}>
                {item.label}
              </option>
            ))}
        </select>
      </Field>
      {hasBoard && (
        <Field
          label="Board identifier"
          hint="Usually detected from the address."
        >
          <input
            name="board"
            key={kind}
            defaultValue={String(source?.config.board || "")}
          />
        </Field>
      )}
    </>
  );
}

/** How much one run collects, within the limits of the source's kind. */
export function AcquisitionFields({
  source,
  search,
  properties,
  defaults,
}: {
  source?: Source;
  search: boolean;
  properties: ConfigProperties;
  defaults: (key: string, fallback: unknown) => unknown;
}) {
  const config = source?.config || {};
  const number = (key: string, fallback: number) =>
    Number(config[key] || defaults(key, fallback));
  return search ? (
    <>
      <Field label="Results per portal" hint="1 to 50; 20 by default.">
        <input
          name="results_wanted"
          type="number"
          min={1}
          max={50}
          required
          defaultValue={number("results_wanted", 20)}
        />
      </Field>
      <Field
        label="Posted within (hours)"
        hint="The age the portals are asked for; 72 by default."
      >
        <input
          name="hours_old"
          type="number"
          min={1}
          max={8760}
          required
          defaultValue={number("hours_old", 72)}
        />
      </Field>
      <Field label="Job type">
        <select name="job_type" defaultValue={String(config.job_type || "")}>
          <option value="">Any type</option>
          {JOB_TYPES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </Field>
      <label className="toggle">
        <input
          name="is_remote"
          type="checkbox"
          defaultChecked={!!config.is_remote}
        />
        Remote roles only
      </label>
    </>
  ) : Object.hasOwn(properties, "max_results") ? (
    <Field label="Results per run" hint="1 to 2,000; 100 by default.">
      <input
        name="max_results"
        type="number"
        min={1}
        max={2000}
        required
        defaultValue={number("max_results", 100)}
      />
    </Field>
  ) : null;
}

/** Run-only or bulk limits: the acquisition limits every chosen source shares. */
export function SharedLimits({
  properties,
  placeholder,
}: {
  properties: ConfigProperties;
  placeholder: string;
}) {
  const fields = LIMITS.filter(({ key }) => Object.hasOwn(properties, key));
  return fields.length ? (
    <div className="form-grid">
      {fields.map(({ key, label }) => (
        <Field label={label} key={key}>
          <input
            name={key}
            type="number"
            min={properties[key].minimum}
            max={properties[key].maximum}
            placeholder={placeholder}
          />
        </Field>
      ))}
    </div>
  ) : (
    <p className="muted">The chosen sources share no acquisition limit.</p>
  );
}

/** Title and location filters, applied to every listing the source returns. */
export function FilterFields({ source }: { source?: Source }) {
  const value = (key: string) =>
    ((source?.filters[key] as string[]) || []).join(", ");
  return (
    <>
      <Field
        label="Titles to keep"
        hint="Optional, separated by commas; any term matches."
      >
        <input
          name="titles"
          defaultValue={value("titles")}
          placeholder="engineer, developer"
        />
      </Field>
      <Field label="Locations to keep" hint="Optional, separated by commas.">
        <input
          name="locations"
          defaultValue={value("locations")}
          placeholder="Switzerland, remote"
        />
      </Field>
      <Field
        label="Words to leave out"
        hint="Optional whole words; a title with any of them is skipped."
      >
        <input
          name="exclude_titles"
          defaultValue={value("exclude_titles")}
          placeholder="intern, working student"
        />
      </Field>
    </>
  );
}
