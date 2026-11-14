// The sentence under "Today": what waits for the owner, in one breath.

const count = (n: number, one: string, many = one + "s") =>
  `${n} ${n === 1 ? one : many}`;

export interface TodayCounts {
  ready: number;
  blocked: number;
  /** Applications that waited more than `days` for a reply. */
  waiting: number;
  days: number;
}
export interface Summary {
  /** The first sentence, shown strong. */
  lead: string;
  rest: string;
  /** True when nothing waits for the owner. */
  quiet: boolean;
}

const capital = (text: string) => text[0].toUpperCase() + text.slice(1);
function sentence(clauses: string[]) {
  if (!clauses.length) return "";
  const last = clauses[clauses.length - 1];
  const text =
    clauses.length === 1
      ? last
      : `${clauses.slice(0, -1).join(", ")}, and ${last}`;
  return capital(text) + ".";
}

export function todaySummary(counts: TodayCounts): Summary {
  const clauses: string[] = [];
  if (counts.blocked)
    clauses.push(
      `${count(counts.blocked, "application")} ${counts.blocked === 1 ? "is" : "are"} blocked by a requirement`,
    );
  if (counts.waiting)
    clauses.push(
      `${count(counts.waiting, "application")} ${counts.waiting === 1 ? "has" : "have"} waited more than ${counts.days} days for a reply`,
    );
  if (counts.ready)
    return {
      lead: `${count(counts.ready, "application")} ${counts.ready === 1 ? "is" : "are"} ready for you.`,
      rest: sentence(clauses),
      quiet: false,
    };
  if (clauses.length)
    return {
      lead: sentence(clauses.slice(0, 1)),
      rest: sentence(clauses.slice(1)),
      quiet: false,
    };
  return { lead: "Nothing is waiting for you.", rest: "", quiet: true };
}
