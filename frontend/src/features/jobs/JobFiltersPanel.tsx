import { Button, Card, Chip, Input } from "@heroui/react";
import { ChevronDown, RotateCcw, Search, SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";

import type { FacetsResponse, JobRecord } from "../../api/types";
import type { JobFilterValues } from "./jobFilters";

interface JobFiltersPanelProps {
  facets?: FacetsResponse;
  filters: JobFilterValues;
  onChange: (patch: Partial<JobFilterValues>) => void;
  onClearSelection: () => void;
  onReset: () => void;
  onSelectVisible: () => void;
  selectedCount: number;
  visibleJobs: JobRecord[];
}

export function JobFiltersPanel({
  facets,
  filters,
  onChange,
  onClearSelection,
  onReset,
  onSelectVisible,
  selectedCount,
  visibleJobs
}: JobFiltersPanelProps) {
  const activeAdvancedCount = useMemo(
    () =>
      [
        filters.company,
        filters.location,
        filters.site,
        filters.jobType,
        filters.minScore,
        filters.maxScore,
        filters.minSalary,
        filters.maxSalary,
        filters.datePostedFrom,
        filters.datePostedTo
      ].filter(Boolean).length,
    [filters]
  );
  const [showAdvanced, setShowAdvanced] = useState(activeAdvancedCount > 0);

  return (
    <Card className="border border-zinc-200 bg-white shadow-sm" variant="default">
      <div className="grid gap-4 p-4">
        <div className="grid gap-3 xl:grid-cols-[minmax(320px,1fr)_auto_180px_auto] xl:items-end">
          <label className="grid gap-1.5 text-sm font-medium text-zinc-700">
            <span>Search</span>
            <div className="relative">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2 text-zinc-400"
                size={16}
              />
              <Input
                aria-label="Search jobs"
                className="pl-9"
                fullWidth
                onChange={(event) => onChange({ text: event.target.value })}
                placeholder="Search title, company, location"
                value={filters.text}
                variant="secondary"
              />
            </div>
          </label>

          <div className="grid gap-1.5">
            <span className="text-sm font-medium text-zinc-700">Status</span>
            <div aria-label="Status" className="flex flex-wrap gap-1.5" role="group">
              <StatusButton
                isSelected={filters.status === "all"}
                label="All"
                onPress={() => onChange({ status: "all" })}
              />
              <StatusButton
                isSelected={filters.status === "open"}
                label="Open"
                onPress={() => onChange({ status: "open" })}
              />
              <StatusButton
                isSelected={filters.status === "bookmarked"}
                label="Saved"
                onPress={() => onChange({ status: "bookmarked" })}
              />
              <StatusButton
                isSelected={filters.status === "applied"}
                label="Applied"
                onPress={() => onChange({ status: "applied" })}
              />
            </div>
          </div>

          <label className="grid gap-1.5 text-sm font-medium text-zinc-700">
            <span>Sort</span>
            <select
              aria-label="Sort"
              className="h-10 rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950 shadow-sm outline-none focus:border-zinc-950 focus:ring-2 focus:ring-zinc-100"
              onChange={(event) => onChange({ sort: event.target.value as JobFilterValues["sort"] })}
              value={filters.sort}
            >
              <option value="score">Score</option>
              <option value="date">Date</option>
              <option value="company">Company</option>
              <option value="title">Title</option>
              <option value="salary">Salary</option>
            </select>
          </label>

          <label className="flex h-10 items-center gap-2 text-sm font-semibold text-zinc-700 xl:justify-end">
            <input
              checked={filters.remoteOnly}
              className="size-4 accent-zinc-950"
              onChange={(event) => onChange({ remoteOnly: event.target.checked })}
              type="checkbox"
            />
            Remote
          </label>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-zinc-100 pt-3">
          <Button onPress={() => setShowAdvanced((value) => !value)} variant="outline">
            <SlidersHorizontal aria-hidden="true" size={16} />
            More filters
            {activeAdvancedCount > 0 ? (
              <Chip className="ml-1" color="default" size="sm" variant="soft">
                {activeAdvancedCount}
              </Chip>
            ) : null}
            <ChevronDown
              aria-hidden="true"
              className={showAdvanced ? "rotate-180 transition-transform" : "transition-transform"}
              size={16}
            />
          </Button>

          <div className="flex flex-wrap gap-2">
            <Button onPress={onReset} variant="outline">
              <RotateCcw aria-hidden="true" size={16} />
              Reset filters
            </Button>
            <Button isDisabled={visibleJobs.length === 0} onPress={onSelectVisible} variant="outline">
              Select visible
            </Button>
            <Button isDisabled={selectedCount === 0} onPress={onClearSelection} variant="outline">
              Clear selection
            </Button>
          </div>
        </div>

        {showAdvanced ? (
          <div className="grid gap-4 border-t border-zinc-100 pt-4 xl:grid-cols-[1.15fr_1fr_0.85fr]">
            <fieldset className="grid gap-3">
              <legend className="mb-1 text-xs font-bold uppercase text-zinc-500">Source</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                <TextFilter
                  label="Company"
                  name="Company"
                  onChange={(value) => onChange({ company: value })}
                  value={filters.company}
                />
                <TextFilter
                  label="Location"
                  name="Location"
                  onChange={(value) => onChange({ location: value })}
                  value={filters.location}
                />
                <TextFilter
                  datalistId="job-sites"
                  label="Site"
                  name="Site"
                  onChange={(value) => onChange({ site: value })}
                  value={filters.site}
                />
                <TextFilter
                  datalistId="job-types"
                  label="Job type"
                  name="Job type"
                  onChange={(value) => onChange({ jobType: value })}
                  value={filters.jobType}
                />
              </div>
              <datalist id="job-sites">
                {(facets?.sites ?? []).map((facet) => (
                  <option key={String(facet.value)} value={String(facet.value)} />
                ))}
              </datalist>
              <datalist id="job-types">
                {(facets?.job_types ?? []).map((facet) => (
                  <option key={String(facet.value)} value={String(facet.value)} />
                ))}
              </datalist>
            </fieldset>

            <fieldset className="grid gap-3">
              <legend className="mb-1 text-xs font-bold uppercase text-zinc-500">Score and salary</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                <NumberFilter
                  label="Min score"
                  max="100"
                  min="0"
                  name="Minimum score"
                  onChange={(value) => onChange({ minScore: value })}
                  value={filters.minScore}
                />
                <NumberFilter
                  label="Max score"
                  max="100"
                  min="0"
                  name="Maximum score"
                  onChange={(value) => onChange({ maxScore: value })}
                  value={filters.maxScore}
                />
                <NumberFilter
                  label="Min salary"
                  min="0"
                  name="Minimum salary"
                  onChange={(value) => onChange({ minSalary: value })}
                  value={filters.minSalary}
                />
                <NumberFilter
                  label="Max salary"
                  min="0"
                  name="Maximum salary"
                  onChange={(value) => onChange({ maxSalary: value })}
                  value={filters.maxSalary}
                />
              </div>
            </fieldset>

            <fieldset className="grid gap-3">
              <legend className="mb-1 text-xs font-bold uppercase text-zinc-500">Posted date</legend>
              <label className="grid gap-1.5 text-sm font-medium text-zinc-700">
                <span>From</span>
                <Input
                  aria-label="Date posted from"
                  onChange={(event) => onChange({ datePostedFrom: event.target.value })}
                  type="date"
                  value={filters.datePostedFrom}
                  variant="secondary"
                />
              </label>
              <label className="grid gap-1.5 text-sm font-medium text-zinc-700">
                <span>To</span>
                <Input
                  aria-label="Date posted to"
                  onChange={(event) => onChange({ datePostedTo: event.target.value })}
                  type="date"
                  value={filters.datePostedTo}
                  variant="secondary"
                />
              </label>
            </fieldset>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

function StatusButton({
  isSelected,
  label,
  onPress
}: {
  isSelected: boolean;
  label: string;
  onPress: () => void;
}) {
  return (
    <Button
      aria-pressed={isSelected}
      className="min-w-16"
      onPress={onPress}
      variant={isSelected ? "secondary" : "outline"}
    >
      {label}
    </Button>
  );
}

function TextFilter({
  datalistId,
  label,
  name,
  onChange,
  value
}: {
  datalistId?: string;
  label: string;
  name: string;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <label className="grid gap-1.5 text-sm font-medium text-zinc-700">
      <span>{label}</span>
      <Input
        aria-label={name}
        list={datalistId}
        onChange={(event) => onChange(event.target.value)}
        value={value}
        variant="secondary"
      />
    </label>
  );
}

function NumberFilter({
  label,
  max,
  min,
  name,
  onChange,
  value
}: {
  label: string;
  max?: string;
  min: string;
  name: string;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <label className="grid gap-1 text-sm font-medium text-zinc-700">
      <span>{label}</span>
      <Input
        aria-label={name}
        max={max}
        min={min}
        onChange={(event) => onChange(event.target.value)}
        type="number"
        value={value}
        variant="secondary"
      />
    </label>
  );
}
