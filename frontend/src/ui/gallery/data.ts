// Synthetic records for the gallery. No real people, companies or postings.

/** A fixed "now" so the gallery reads the same on every run. */
export const NOW = new Date(2026, 10, 14, 15, 0);

export const PROVIDERS = [
  {
    name: "Greenhouse",
    status: "Ready",
    tone: "success",
    spacing: 2,
    day: 142,
  },
  {
    name: "LinkedIn",
    status: "Waiting",
    tone: "warning",
    spacing: 30,
    day: 18,
  },
  {
    name: "Fjord board",
    status: "Failed",
    tone: "danger",
    spacing: 10,
    day: 0,
  },
  { name: "Lever", status: "Ready", tone: "success", spacing: 5, day: 1_204 },
] as const;
