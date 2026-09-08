import type { JobListParams } from "../../api/types";

/** The filters kept in the URL, so a filtered Inbox is a link you can share. */
export type InboxFilters = Pick<
  JobListParams,
  | "sources"
  | "labels"
  | "company"
  | "location"
  | "job_types"
  | "remote"
  | "min_score"
  | "max_score"
  | "first_seen_from"
  | "first_seen_to"
  | "has_attachments"
  | "without_labels"
>;

export const LIST_KEYS = ["sources", "labels", "job_types"] as const;
export const TEXT_KEYS = ["company", "location", "first_seen_from", "first_seen_to"] as const;
export const NUMBER_KEYS = ["min_score", "max_score"] as const;
export const BOOL_KEYS = ["remote", "has_attachments", "without_labels"] as const;
export const FILTER_KEYS = [...LIST_KEYS, ...TEXT_KEYS, ...NUMBER_KEYS, ...BOOL_KEYS];

export function paramsToFilters(params: URLSearchParams): InboxFilters {
  const filters: InboxFilters = {};
  for (const key of LIST_KEYS) {
    const values = params.getAll(key).filter(Boolean);
    if (values.length) {
      filters[key] = values;
    }
  }
  for (const key of TEXT_KEYS) {
    const value = params.get(key);
    if (value) {
      filters[key] = value;
    }
  }
  for (const key of NUMBER_KEYS) {
    const value = params.get(key);
    if (value !== null && value !== "" && !Number.isNaN(Number(value))) {
      filters[key] = Number(value);
    }
  }
  for (const key of BOOL_KEYS) {
    const value = params.get(key);
    if (value === "true") {
      filters[key] = true;
    } else if (value === "false") {
      filters[key] = false;
    }
  }
  return filters;
}

export function activeFilterCount(filters: InboxFilters): number {
  return Object.values(filters).filter((value) =>
    Array.isArray(value) ? value.length > 0 : value !== undefined,
  ).length;
}

/** A `setParams` patch that clears every filter. */
export function clearedFilters(): Record<string, null> {
  return Object.fromEntries(FILTER_KEYS.map((key) => [key, null]));
}
