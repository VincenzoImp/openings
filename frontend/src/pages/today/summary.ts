// The sentence under "Today": what waits for the owner, in one breath.

const count = (n: number, one: string, many = one + "s") =>
  `${n} ${n === 1 ? one : many}`;

export interface TodayCounts {
  ready: number;
  questions: number;
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

/** `lastRun` says what the agent last did, for the day nothing is waiting. */
export function todaySummary(counts: TodayCounts, lastRun = ""): Summary {
  const clauses: string[] = [];
  if (counts.questions)
    clauses.push(`your agent has ${count(counts.questions, "question")}`);
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
  return { lead: "Nothing is waiting for you.", rest: lastRun, quiet: true };
}

/** Days after which an application counts as waiting long, when the policy does not say. */
export const DEFAULT_REPLY_DAYS = 30;
/** The period of the policy's "No reply" decision item: a number, or text such as "45 days". */
export function replyDays(items: { label: string; value: unknown }[]) {
  for (const item of items) {
    if (!/\bno[\s-]?(reply|response)\b/i.test(item.label)) continue;
    const text =
      typeof item.value === "number"
        ? String(item.value)
        : typeof item.value === "string"
          ? (/^\s*(\d{1,4})(\s*days?)?\s*$/i.exec(item.value)?.[1] ?? "")
          : "";
    const days = text ? Number(text) : NaN;
    if (Number.isInteger(days) && days >= 1 && days <= 3650) return days;
  }
  return DEFAULT_REPLY_DAYS;
}
