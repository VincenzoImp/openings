import { X } from "lucide-react";

import { setParams } from "../../app/router";
import { clearedFilters } from "./filters";
import type { InboxFilters } from "./filters";

interface Chip {
  key: string;
  label: string;
  clear: () => void;
}

function chips(filters: InboxFilters): Chip[] {
  const out: Chip[] = [];
  const list = (key: "sources" | "labels" | "job_types", name: string) => {
    for (const value of filters[key] ?? []) {
      out.push({
        key: `${key}:${value}`,
        label: `${name}: ${value}`,
        clear: () => setParams({ [key]: (filters[key] ?? []).filter((item) => item !== value) }),
      });
    }
  };
  list("sources", "source");
  list("labels", "label");
  list("job_types", "type");
  if (filters.company) {
    out.push({
      key: "company",
      label: `company: ${filters.company}`,
      clear: () => setParams({ company: null }),
    });
  }
  if (filters.location) {
    out.push({
      key: "location",
      label: `location: ${filters.location}`,
      clear: () => setParams({ location: null }),
    });
  }
  if (filters.min_score !== undefined) {
    out.push({
      key: "min",
      label: `score ≥ ${filters.min_score}`,
      clear: () => setParams({ min_score: null }),
    });
  }
  if (filters.max_score !== undefined) {
    out.push({
      key: "max",
      label: `score ≤ ${filters.max_score}`,
      clear: () => setParams({ max_score: null }),
    });
  }
  if (filters.first_seen_from) {
    out.push({
      key: "from",
      label: `seen from ${filters.first_seen_from}`,
      clear: () => setParams({ first_seen_from: null }),
    });
  }
  if (filters.first_seen_to) {
    out.push({
      key: "to",
      label: `seen to ${filters.first_seen_to}`,
      clear: () => setParams({ first_seen_to: null }),
    });
  }
  if (filters.remote !== undefined) {
    out.push({
      key: "remote",
      label: filters.remote ? "remote only" : "on site only",
      clear: () => setParams({ remote: null }),
    });
  }
  if (filters.has_attachments !== undefined) {
    out.push({
      key: "files",
      label: filters.has_attachments ? "with files" : "without files",
      clear: () => setParams({ has_attachments: null }),
    });
  }
  if (filters.without_labels) {
    out.push({
      key: "unlabelled",
      label: "without labels",
      clear: () => setParams({ without_labels: null }),
    });
  }
  return out;
}

/** What is narrowing the list right now, each removable with one click. */
export function ActiveFilters({ filters }: { filters: InboxFilters }) {
  const items = chips(filters);
  if (items.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-wrap items-center gap-1" aria-label="Active filters">
      {items.map((chip) => (
        <span
          key={chip.key}
          className="inline-flex items-center gap-1 rounded-full border border-accent/40 bg-accent/8 px-2 py-0.5 text-xs text-fg"
        >
          {chip.label}
          <button
            type="button"
            aria-label={`Remove filter ${chip.label}`}
            className="rounded-full text-fg-muted hover:text-fg"
            onClick={chip.clear}
          >
            <X size={12} aria-hidden="true" />
          </button>
        </span>
      ))}
      {items.length > 1 ? (
        <button
          type="button"
          className="text-xs text-fg-muted underline hover:text-fg"
          onClick={() => setParams(clearedFilters())}
        >
          Clear all
        </button>
      ) : null}
    </div>
  );
}
