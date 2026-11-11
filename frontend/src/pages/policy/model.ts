// Words and conversions of the Policy screen, kept free of React.
import type {
  PolicyItem,
  PolicyRule,
  PolicySectionName,
  PolicySignal,
  PolicyValueType,
} from "../../api";

export const sectionWords: Record<
  PolicySectionName,
  { item: string; add: string; empty: string }
> = {
  decision: {
    item: "rule",
    add: "Add a rule",
    empty:
      "No rules yet. Say once what to shortlist and what to dismiss, in your own words.",
  },
  eligibility: {
    item: "fact",
    add: "Add a fact",
    empty:
      "No facts yet. Record what employers ask about: work authorization, start date, relocation.",
  },
  writing: {
    item: "rule",
    add: "Add a rule",
    empty:
      "No rules yet. Say how your CV and letters should be written, and what they never say.",
  },
  facts: {
    item: "fact",
    add: "Add a fact",
    empty:
      "No facts yet. Anything else you confirm once, such as a notice period, belongs here.",
  },
};
export const scopeLabels = { all: "All documents", cv: "CV", letter: "Letter" };
export const valueTypeLabels: Record<
  Exclude<PolicyValueType, "structured">,
  string
> = {
  text: "Text",
  number: "Number",
  date: "Date",
  boolean: "Yes or no",
  list: "List",
};
const operatorWords: Record<string, string> = {
  in: "is one of",
  not_in: "is none of",
  at_least: "is at least",
  is: "is",
};
export const actionWords: Record<string, string> = {
  dismiss: "Dismiss the job",
  flag: "Flag the job",
};

const MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");
/** A stored date (YYYY, YYYY-MM or YYYY-MM-DD) in words, without a time zone. */
export function plainDate(value: string) {
  const [year, month, day] = value.split("-");
  if (!month) return year;
  const name = MONTHS[Number(month) - 1] || month;
  return day ? `${Number(day)} ${name} ${year}` : `${name} ${year}`;
}

/** The value of an item as one line of text; null for a structured value. */
export function valueText(item: Pick<PolicyItem, "value" | "value_type">) {
  const { value, value_type: type } = item;
  if (type === null || value === null || type === "structured") return null;
  if (type === "list") return (value as string[]).join(" · ");
  if (type === "boolean") return value ? "Yes" : "No";
  if (type === "date") return plainDate(String(value));
  return String(value);
}

export function ruleText(rule: PolicyRule, signals: PolicySignal[]) {
  const signal = signals.find((item) => item.signal === rule.signal);
  const { operator, value } = rule.condition;
  const shown = Array.isArray(value)
    ? value.join(", ")
    : typeof value === "boolean"
      ? value
        ? "true"
        : "false"
      : String(value);
  return `${actionWords[rule.action] || rule.action} when ${(
    signal?.label || rule.signal
  ).toLowerCase()} ${operatorWords[operator] || operator} ${shown}`;
}

/** What the form holds while an item is written; every field is text. */
export interface ItemDraft {
  label: string;
  statement: string;
  note: string;
  scope: "all" | "cv" | "letter";
  /** "keep" leaves a structured value as it was copied. */
  valueType: "none" | "keep" | Exclude<PolicyValueType, "structured">;
  value: string;
  signal: string;
  operator: string;
  ruleValue: string;
  action: string;
}

export function draftOf(item?: PolicyItem): ItemDraft {
  const type = item?.value_type ?? null;
  return {
    label: item?.label ?? "",
    statement: item?.statement ?? "",
    note: item?.note ?? "",
    scope: item?.scope ?? "all",
    valueType: type === null ? "none" : type === "structured" ? "keep" : type,
    value:
      type === null || type === "structured"
        ? ""
        : type === "list"
          ? (item!.value as string[]).join(", ")
          : String(item!.value),
    signal: item?.rule?.signal ?? "",
    operator: item?.rule?.condition.operator ?? "",
    ruleValue: Array.isArray(item?.rule?.condition.value)
      ? (item!.rule!.condition.value as string[]).join(", ")
      : String(item?.rule?.condition.value ?? ""),
    action: item?.rule?.action ?? "dismiss",
  };
}

const items = (text: string) =>
  text
    .split(/[,\n]/)
    .map((part) => part.trim())
    .filter(Boolean);

function typed(type: string, text: string): unknown {
  if (type === "number") return Number(text);
  if (type === "boolean") return text === "true";
  if (type === "list") return items(text);
  return text.trim();
}

/** The request body of a draft. Throws an Error with a sentence when it cannot be sent. */
export function bodyOf(
  draft: ItemDraft,
  section: PolicySectionName,
  signals: PolicySignal[],
) {
  const body: Record<string, unknown> = {
    label: draft.label.trim(),
    statement: draft.statement.trim(),
    note: draft.note.trim(),
  };
  if (section === "writing") body.scope = draft.scope;
  if (draft.valueType === "none") body.value = null;
  else if (draft.valueType !== "keep") {
    if (draft.valueType === "number" && !Number.isFinite(Number(draft.value)))
      throw Error("The value needs a number.");
    if (draft.valueType !== "boolean" && !draft.value.trim())
      throw Error("Enter the value, or choose “No value”.");
    body.value = typed(draft.valueType, draft.value);
    body.value_type = draft.valueType;
  }
  if (section === "decision") {
    const signal = signals.find((item) => item.signal === draft.signal);
    if (!signal) body.rule = null;
    else {
      const operator =
        signal.operators.find((item) => item.operator === draft.operator) ||
        signal.operators[0];
      const value =
        operator.value_type === "boolean"
          ? true
          : typed(operator.value_type, draft.ruleValue);
      if (operator.value_type === "list" && !(value as string[]).length)
        throw Error("List the values the signal is compared with.");
      if (
        operator.value_type === "number" &&
        (draft.ruleValue.trim() === "" || !Number.isFinite(value as number))
      )
        throw Error("The rule needs a number between 0 and 1.");
      body.rule = {
        signal: signal.signal,
        condition: { operator: operator.operator, value },
        action: draft.action,
      };
    }
  }
  return body;
}
