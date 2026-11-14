import { useState } from "react";
import { Check, ChevronLeft, ChevronRight } from "lucide-react";
import { SearchField, Switch } from "../../ui/Field";
import { formatNumber } from "../../ui/format";
import { Icon } from "../../ui/Icon";
import { useFacets } from "./data";
import {
  DISMISSED_BY,
  LANGUAGES,
  POSTING_LANGUAGES,
  SIGNALS,
  SORTS,
  chipsOf,
  foundChoices,
  languageName,
  sortsOf,
  sourceName,
  unspokenLine,
  type FilterKey,
  type ListQuery,
  type Sort,
  type View,
} from "./model";

type Field = FilterKey | "sort";
interface Choice {
  value: string;
  label: string;
  count?: number;
}

const LABELS: Record<Exclude<Field, "hide_unspoken">, string> = {
  sort: "Sort",
  source: "Source",
  company: "Company",
  location: "Location",
  posting_language: "Posting language",
  requires: "Required language",
  signal: "Label",
  created_since: "Found",
  dismissed_by: "Dismissed by",
};
const FACETS: Partial<Record<Field, string>> = {
  source: "sources",
  company: "companies",
  location: "locations",
};

/**
 * The filters of the list, as a menu of fields and then the values of one
 * field. In a popover on wide screens, in a bottom sheet on a phone (where
 * Sort joins them). "Hide jobs requiring languages I don't speak" says how
 * many jobs it would hide.
 */
export function FilterPanel({
  view,
  query,
  withSort = false,
  unspoken,
  total,
  dismissedCounts,
  onFilter,
  onSort,
}: {
  view: View;
  query: ListQuery;
  withSort?: boolean;
  unspoken?: {
    count?: unknown;
    hidden?: unknown;
    spoken_languages?: unknown;
  } | null;
  total: number;
  dismissedCounts?: Record<string, number>;
  onFilter: (key: FilterKey, value: string) => void;
  onSort: (sort: Sort) => void;
}) {
  const [field, setField] = useState<Field | null>(null);
  const [typed, setTyped] = useState("");
  const facets = useFacets(query, !!field && field in FACETS);
  const chips = chipsOf(view);
  const fields: Field[] = [
    ...(withSort ? (["sort"] as const) : []),
    "source",
    "company",
    "location",
    "posting_language",
    "requires",
    "signal",
    "created_since",
    ...(view.section === "dismissed" ? (["dismissed_by"] as const) : []),
  ];
  function choices(of: Field): Choice[] {
    if (of === "sort")
      return sortsOf(view.section).map((sort) => ({
        value: sort,
        label: SORTS[sort],
      }));
    const facet = FACETS[of];
    if (facet)
      return (facets.data?.[facet] ?? []).map((value) => ({
        value,
        label: of === "source" ? sourceName(value) : value,
      }));
    if (of === "posting_language")
      return POSTING_LANGUAGES.map((code) => ({
        value: code,
        label: languageName(code),
      }));
    if (of === "requires")
      return Object.entries(LANGUAGES).map(([value, label]) => ({
        value,
        label,
      }));
    if (of === "signal")
      return Object.entries(SIGNALS).map(([value, label]) => ({
        value,
        label,
      }));
    if (of === "created_since") return foundChoices();
    if (of === "dismissed_by")
      return Object.entries(DISMISSED_BY).map(([value, label]) => ({
        value,
        label,
        count: dismissedCounts?.[value],
      }));
    return [];
  }
  const current = (of: Field) =>
    of === "sort" ? view.sort : view.filters[of as FilterKey];
  const shown = (of: Field) => {
    if (of === "sort") return SORTS[view.sort];
    return chips.find((chip) => chip.key === of)?.value ?? "Any";
  };

  if (field) {
    const all = choices(field);
    const list = typed
      ? all.filter((choice) =>
          choice.label.toLowerCase().includes(typed.toLowerCase()),
        )
      : all;
    const pick = (value: string) => {
      if (field === "sort") onSort(value as Sort);
      else onFilter(field as FilterKey, value);
      setField(null);
      setTyped("");
    };
    const label = LABELS[field as keyof typeof LABELS];
    return (
      <div className="jobs-filter" role="group" aria-label={label}>
        <button
          type="button"
          className="ui-menu-item jobs-filter-back"
          onClick={() => {
            setField(null);
            setTyped("");
          }}
        >
          <Icon icon={ChevronLeft} size="sm" />
          {label}
        </button>
        {all.length > 8 && (
          <SearchField
            label={`Search ${label.toLowerCase()}`}
            value={typed}
            autoFocus
            onChange={(event) => setTyped(event.target.value)}
          />
        )}
        <ul className="jobs-filter-list">
          {field !== "sort" && (
            <li>
              <button
                type="button"
                className="ui-menu-item"
                aria-pressed={!current(field)}
                onClick={() => pick("")}
              >
                <span className="ui-menu-label">Any</span>
                {!current(field) && <Icon icon={Check} size="sm" />}
              </button>
            </li>
          )}
          {list.map((choice) => (
            <li key={choice.value}>
              <button
                type="button"
                className="ui-menu-item"
                aria-pressed={current(field) === choice.value}
                onClick={() => pick(choice.value)}
              >
                <span className="ui-menu-label">{choice.label}</span>
                {choice.count != null && (
                  <span className="ui-count">{formatNumber(choice.count)}</span>
                )}
                {current(field) === choice.value && (
                  <Icon icon={Check} size="sm" />
                )}
              </button>
            </li>
          ))}
          {!list.length && (
            <li className="jobs-filter-none">
              {facets.isFetching ? "Loading…" : "Nothing to choose from"}
            </li>
          )}
        </ul>
      </div>
    );
  }

  const spoken = Array.isArray(unspoken?.spoken_languages)
    ? unspoken.spoken_languages.length
    : 0;
  return (
    <div className="jobs-filter">
      <ul className="jobs-filter-list">
        {fields.map((of) => (
          <li key={of}>
            <button
              type="button"
              className="ui-menu-item"
              onClick={() => setField(of)}
            >
              <span className="ui-menu-label">
                {LABELS[of as keyof typeof LABELS]}
              </span>
              <span className="jobs-filter-value">{shown(of)}</span>
              <Icon icon={ChevronRight} size="sm" />
            </button>
          </li>
        ))}
      </ul>
      <div className="jobs-filter-switch">
        {spoken ? (
          <Switch
            label="Hide jobs requiring languages I don't speak"
            hint={unspokenLine(unspoken, total) || undefined}
            checked={view.filters.hide_unspoken === "true"}
            onChange={(event) =>
              onFilter("hide_unspoken", event.target.checked ? "true" : "")
            }
          />
        ) : (
          <p className="jobs-muted">
            To hide jobs requiring languages you don't speak, list yours in{" "}
            <a href="#preferences">Preferences</a>.
          </p>
        )}
      </div>
    </div>
  );
}
