import { setParams } from "../../app/router";
import { Button } from "../../components/Button";
import { Dialog } from "../../components/Dialog";
import { Checkbox, Field, Input, Select } from "../../components/Field";
import { useFacets } from "../shared/queries";
import { clearedFilters } from "./filters";
import type { InboxFilters } from "./filters";

function toggleIn(list: string[] | undefined, value: string): string[] {
  const current = list ?? [];
  return current.includes(value) ? current.filter((item) => item !== value) : [...current, value];
}

export function FilterDrawer({
  open,
  onClose,
  filters,
}: {
  open: boolean;
  onClose: () => void;
  filters: InboxFilters;
}) {
  const facets = useFacets({ limit: 30 }, open);

  return (
    <Dialog
      open={open}
      title="Filters"
      onClose={onClose}
      wide
      footer={
        <>
          <Button onClick={() => setParams(clearedFilters())}>Clear All</Button>
          <Button variant="primary" onClick={onClose}>
            Done
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <fieldset className="min-w-0">
          <legend className="mb-1 text-xs font-medium text-fg-muted">Sources</legend>
          <div className="flex flex-wrap gap-2">
            {(facets.data?.sources ?? []).map((facet) => (
              <Checkbox
                key={facet.value}
                label={`${facet.value} (${facet.count})`}
                checked={filters.sources?.includes(facet.value) ?? false}
                onChange={() => setParams({ sources: toggleIn(filters.sources, facet.value) })}
              />
            ))}
          </div>
        </fieldset>
        <fieldset className="min-w-0">
          <legend className="mb-1 text-xs font-medium text-fg-muted">Labels</legend>
          <div className="flex flex-wrap gap-2">
            {(facets.data?.labels ?? []).map((facet) => (
              <Checkbox
                key={facet.value}
                label={`${facet.value} (${facet.count})`}
                checked={filters.labels?.includes(facet.value) ?? false}
                onChange={() => setParams({ labels: toggleIn(filters.labels, facet.value) })}
              />
            ))}
            {facets.data && facets.data.labels.length === 0 ? (
              <span className="text-xs text-fg-faint">No labels yet.</span>
            ) : null}
          </div>
        </fieldset>
        <fieldset className="min-w-0">
          <legend className="mb-1 text-xs font-medium text-fg-muted">Job types</legend>
          <div className="flex flex-wrap gap-2">
            {(facets.data?.job_types ?? []).map((facet) => (
              <Checkbox
                key={facet.value}
                label={`${facet.value} (${facet.count})`}
                checked={filters.job_types?.includes(facet.value) ?? false}
                onChange={() => setParams({ job_types: toggleIn(filters.job_types, facet.value) })}
              />
            ))}
          </div>
        </fieldset>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Company" htmlFor="filter-company" className="col-span-2">
            <Input
              id="filter-company"
              list="filter-companies"
              value={filters.company ?? ""}
              onChange={(event) => setParams({ company: event.target.value })}
              autoComplete="off"
            />
            <datalist id="filter-companies">
              {(facets.data?.companies ?? []).map((facet) => (
                <option key={facet.value} value={facet.value} />
              ))}
            </datalist>
          </Field>
          <Field label="Location" htmlFor="filter-location" className="col-span-2">
            <Input
              id="filter-location"
              list="filter-locations"
              value={filters.location ?? ""}
              onChange={(event) => setParams({ location: event.target.value })}
              autoComplete="off"
            />
            <datalist id="filter-locations">
              {(facets.data?.locations ?? []).map((facet) => (
                <option key={facet.value} value={facet.value} />
              ))}
            </datalist>
          </Field>
          <Field label="Min score" htmlFor="filter-min">
            <Input
              id="filter-min"
              type="number"
              inputMode="numeric"
              value={filters.min_score ?? ""}
              onChange={(event) => setParams({ min_score: event.target.value })}
            />
          </Field>
          <Field label="Max score" htmlFor="filter-max">
            <Input
              id="filter-max"
              type="number"
              inputMode="numeric"
              value={filters.max_score ?? ""}
              onChange={(event) => setParams({ max_score: event.target.value })}
            />
          </Field>
          <Field label="First seen from" htmlFor="filter-from">
            <Input
              id="filter-from"
              type="date"
              value={filters.first_seen_from ?? ""}
              onChange={(event) => setParams({ first_seen_from: event.target.value })}
            />
          </Field>
          <Field label="First seen to" htmlFor="filter-to">
            <Input
              id="filter-to"
              type="date"
              value={filters.first_seen_to ?? ""}
              onChange={(event) => setParams({ first_seen_to: event.target.value })}
            />
          </Field>
          <Field label="Remote" htmlFor="filter-remote">
            <Select
              id="filter-remote"
              value={filters.remote === undefined ? "" : String(filters.remote)}
              onChange={(event) => setParams({ remote: event.target.value || null })}
            >
              <option value="">Any</option>
              <option value="true">Remote only</option>
              <option value="false">On site only</option>
            </Select>
          </Field>
          <Field label="Material" htmlFor="filter-material">
            <Select
              id="filter-material"
              value={
                filters.has_attachments === true
                  ? "with"
                  : filters.has_attachments === false
                    ? "without"
                    : filters.without_labels
                      ? "unlabelled"
                      : ""
              }
              onChange={(event) => {
                const value = event.target.value;
                setParams({
                  has_attachments: value === "with" ? "true" : value === "without" ? "false" : null,
                  without_labels: value === "unlabelled" ? "true" : null,
                });
              }}
            >
              <option value="">Any</option>
              <option value="with">With attachments</option>
              <option value="without">Without attachments</option>
              <option value="unlabelled">Without labels</option>
            </Select>
          </Field>
        </div>
      </div>
    </Dialog>
  );
}
