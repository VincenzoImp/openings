// Addresses of the Applications screen and of an application's review page.

/** The review page of an application, optionally on one of its tabs. */
export const reviewHref = (id: string, tab = "") =>
  `#applications/${encodeURIComponent(id)}${tab ? "?tab=" + tab : ""}`;

/** The Ready stage in Today's order: closest deadline first, then priority. */
export const READY_QUEUE = "#applications?stage=ready&sort=deadline";

/** A stage of the pipeline: `#applications?stage=applied`. */
export const stageHref = (stage: string) =>
  stage === "all" ? "#applications" : `#applications?stage=${stage}`;

export const STATS = "#applications?section=stats";
