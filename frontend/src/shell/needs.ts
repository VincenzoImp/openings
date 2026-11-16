// The words after a "needs you" count in the navigation, read by screen
// readers as "1 new job" or "3 new jobs". No React: tested directly.

const NOUNS = {
  newJobs: ["new job", "new jobs"],
  readyApplications: ["ready application", "ready applications"],
} as const;

export type Needs = keyof typeof NOUNS;

/** "new job" for one, "new jobs" for any other count. */
export const needsLabel = (needs: Needs, count: number) =>
  NOUNS[needs][count === 1 ? 0 : 1];
