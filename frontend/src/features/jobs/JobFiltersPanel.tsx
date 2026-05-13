import { Button, Card, Input } from "@heroui/react";
import { RotateCcw, Search } from "lucide-react";

import type { FacetsResponse, JobRecord } from "../../api/types";
import type { JobFilterValues, StatusFilter } from "./jobFilters";

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
  return (
    <Card className="border border-zinc-200 shadow-sm" variant="default">
      <div className="grid gap-3 p-4">
        <div className="grid gap-3 lg:grid-cols-[minmax(240px,2fr)_repeat(4,minmax(120px,1fr))]">
          <label className="grid gap-1 text-sm font-medium text-zinc-700">
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
          <label className="grid gap-1 text-sm font-medium text-zinc-700">
            <span>Company</span>
            <Input
              aria-label="Company"
              onChange={(event) => onChange({ company: event.target.value })}
              value={filters.company}
              variant="secondary"
            />
          </label>
          <label className="grid gap-1 text-sm font-medium text-zinc-700">
            <span>Location</span>
            <Input
              aria-label="Location"
              onChange={(event) => onChange({ location: event.target.value })}
              value={filters.location}
              variant="secondary"
            />
          </label>
          <label className="grid gap-1 text-sm font-medium text-zinc-700">
            <span>Site</span>
            <Input
              aria-label="Site"
              list="job-sites"
              onChange={(event) => onChange({ site: event.target.value })}
              value={filters.site}
              variant="secondary"
            />
            <datalist id="job-sites">
              {(facets?.sites ?? []).map((facet) => (
                <option key={String(facet.value)} value={String(facet.value)} />
              ))}
            </datalist>
          </label>
          <label className="grid gap-1 text-sm font-medium text-zinc-700">
            <span>Job type</span>
            <Input
              aria-label="Job type"
              list="job-types"
              onChange={(event) => onChange({ jobType: event.target.value })}
              value={filters.jobType}
              variant="secondary"
            />
            <datalist id="job-types">
              {(facets?.job_types ?? []).map((facet) => (
                <option key={String(facet.value)} value={String(facet.value)} />
              ))}
            </datalist>
          </label>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-8">
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
          <label className="grid gap-1 text-sm font-medium text-zinc-700">
            <span>Posted from</span>
            <Input
              aria-label="Date posted from"
              onChange={(event) => onChange({ datePostedFrom: event.target.value })}
              type="date"
              value={filters.datePostedFrom}
              variant="secondary"
            />
          </label>
          <label className="grid gap-1 text-sm font-medium text-zinc-700">
            <span>Posted to</span>
            <Input
              aria-label="Date posted to"
              onChange={(event) => onChange({ datePostedTo: event.target.value })}
              type="date"
              value={filters.datePostedTo}
              variant="secondary"
            />
          </label>
          <label className="grid gap-1 text-sm font-medium text-zinc-700">
            <span>Status</span>
            <select
              aria-label="Status"
              className="h-10 rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950 shadow-sm outline-none focus:border-zinc-950 focus:ring-2 focus:ring-zinc-100"
              onChange={(event) => onChange({ status: event.target.value as StatusFilter })}
              value={filters.status}
            >
              <option value="all">All</option>
              <option value="open">Open</option>
              <option value="bookmarked">Saved</option>
              <option value="applied">Applied</option>
            </select>
          </label>
          <label className="grid gap-1 text-sm font-medium text-zinc-700">
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
        </div>

        <label className="flex h-10 items-center gap-2 text-sm font-semibold text-zinc-700">
          <input
            checked={filters.remoteOnly}
            className="size-4 accent-zinc-950"
            onChange={(event) => onChange({ remoteOnly: event.target.checked })}
            type="checkbox"
          />
          Remote
        </label>
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
    </Card>
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
