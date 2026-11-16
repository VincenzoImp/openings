// The address of one job, in the Jobs tab that lists it. Its own module, so
// the shell (the palette, Add job) links to a job without loading the screen.

/** `#jobs?…&job=<id>` in the tab that holds a job of this triage. */
export function jobLink(id: string, triage?: string | null) {
  if (triage === "new") return { job: id };
  if (triage === "dismissed") return { section: "dismissed", job: id };
  return { section: "all", job: id };
}
