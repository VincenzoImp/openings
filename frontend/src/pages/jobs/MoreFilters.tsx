import { Button, Field } from "../../design";
import {
  LANGUAGES,
  POSTING_LANGUAGES,
  languageName,
  type Filters,
} from "./model";

const TEXT: [keyof Filters, string, string][] = [
  ["company", "Company", "companies"],
  ["location", "Location", "locations"],
  ["source", "Source", "sources"],
  ["job_type", "Job type", "job_types"],
];
const KEYS: (keyof Filters)[] = [
  "company",
  "location",
  "source",
  "job_type",
  "remote",
  "created_since",
  "created_until",
  "posting_language",
  "posting_language_not",
  "requires",
];
// The posting's own language is recognised in four languages; a requirement
// can name any of them.
const LANGUAGE_FILTERS: [keyof Filters, string, string[]][] = [
  ["posting_language", "Written in", POSTING_LANGUAGES],
  ["posting_language_not", "Not written in", POSTING_LANGUAGES],
  ["requires", "Requires", Object.keys(LANGUAGES)],
];

/** The archive's other filters, with the values the jobs found have. */
export function MoreFilters({
  filters,
  facets,
  setFilters,
}: {
  filters: Filters;
  facets: Record<string, string[]>;
  setFilters: (patch: Partial<Filters>) => void;
}) {
  const active = KEYS.filter((key) => filters[key]).length;
  const change = (key: keyof Filters, value: string) =>
    setFilters({ [key]: value, offset: "0" });
  return (
    <details className="more-filters" open={active > 0}>
      <summary>
        More filters{active ? ` (${active} on)` : ""}
        <span className="muted">
          {" "}
          · company, place, source, work style, languages, dates
        </span>
      </summary>
      <div className="form-grid">
        {TEXT.map(([key, label]) => (
          <Field key={key} label={label}>
            <input
              list={`jobs-facet-${key}`}
              value={filters[key]}
              placeholder={`Any ${label.toLowerCase()}`}
              onChange={(event) => change(key, event.target.value)}
            />
          </Field>
        ))}
        <Field label="Work style">
          <select
            value={filters.remote}
            onChange={(event) => change("remote", event.target.value)}
          >
            <option value="">Any</option>
            <option value="true">Remote</option>
            <option value="false">On site or hybrid</option>
          </select>
        </Field>
        {LANGUAGE_FILTERS.map(([key, label, codes]) => (
          <Field key={key} label={label}>
            <select
              value={filters[key]}
              onChange={(event) => change(key, event.target.value)}
            >
              <option value="">Any language</option>
              {codes.map((code) => (
                <option key={code} value={code}>
                  {languageName(code)}
                </option>
              ))}
            </select>
          </Field>
        ))}
        <Field label="Added from">
          <input
            type="date"
            value={filters.created_since}
            onChange={(event) => change("created_since", event.target.value)}
          />
        </Field>
        <Field label="Added through">
          <input
            type="date"
            value={filters.created_until}
            onChange={(event) => change("created_until", event.target.value)}
          />
        </Field>
      </div>
      {TEXT.map(([key, , facet]) => (
        <datalist key={key} id={`jobs-facet-${key}`}>
          {(facets[facet] || []).map((value) => (
            <option key={value} value={value} />
          ))}
        </datalist>
      ))}
      {active > 0 && (
        <div className="row">
          <Button
            size="sm"
            variant="quiet"
            onClick={() =>
              setFilters({
                ...Object.fromEntries(KEYS.map((key) => [key, ""])),
                offset: "0",
              })
            }
          >
            Clear these filters
          </Button>
        </div>
      )}
    </details>
  );
}
