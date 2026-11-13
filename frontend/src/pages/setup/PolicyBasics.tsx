import type { FormEvent } from "react";
import { api, type NoReply, type Policy } from "../../api";
import { Button, Field } from "../../design";
import { useWorkspace } from "../../state";
import { replyDays } from "./model";

// Labels an employer asks about most; any other label is fine.
const SUGGESTED = ["Work authorization", "Start date", "Relocation"];
const NO_REPLY_STATEMENT =
  'Close an application as "no reply" when the employer has not answered in this time.';

/**
 * The two parts of the Policy a new workspace needs first: the facts
 * employers ask about (Eligibility) and the no-reply period (the "No reply"
 * decision item). Policy has every section.
 */
export function PolicyBasics({
  policy,
  noReply,
}: {
  policy: Policy;
  noReply: NoReply | null;
}) {
  const { mutate, pending, notify } = useWorkspace();
  const section = (name: string) =>
    policy.sections.find((item) => item.section === name);
  const eligibility = section("eligibility"),
    decision = section("decision");
  async function addFact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    if (
      await mutate(
        () =>
          api("/policy/eligibility/items", "POST", {
            expected_version: eligibility?.version ?? 0,
            label: String(data.get("label") || "").trim(),
            statement: String(data.get("statement") || "").trim(),
          }),
        "Added to Eligibility.",
      )
    )
      form.reset();
  }
  async function savePeriod(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const days = replyDays(
      String(new FormData(event.currentTarget).get("days")),
    );
    if (!days) return notify("Give a number of days from 1 to 3650.", true);
    const value = `${days} days`;
    const expected_version = decision?.version ?? 0;
    await mutate(
      () =>
        noReply?.source === "policy" && noReply.item_id
          ? api(`/policy/items/${noReply.item_id}`, "PATCH", {
              expected_version,
              value,
              value_type: "text",
            })
          : api("/policy/decision/items", "POST", {
              expected_version,
              label: "No reply",
              statement: NO_REPLY_STATEMENT,
              value,
            }),
      `Applications without an answer after ${value} can be closed as no reply.`,
    );
  }
  return (
    <div className="stack">
      <section className="stack" aria-labelledby="setup-facts">
        <h3 id="setup-facts">What employers ask about</h3>
        {eligibility?.items.length ? (
          <ul className="plain" aria-label="Eligibility facts">
            {eligibility.items.map((item) => (
              <li key={item.id}>
                <strong>{item.label}</strong>
                {item.statement && `: ${item.statement}`}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">
            No fact yet. A work authorization, a start date or whether you would
            relocate: your agent answers application questions with them.
          </p>
        )}
        <form
          className="form-grid"
          aria-label="Add a fact employers ask about"
          onSubmit={addFact}
        >
          <Field label="Fact">
            <input
              name="label"
              required
              maxLength={200}
              list="setup-fact-labels"
              placeholder="Work authorization"
            />
          </Field>
          <Field label="What is true for you" className="wide">
            <textarea
              name="statement"
              rows={2}
              maxLength={10000}
              placeholder="EU citizen with a Swiss B permit."
            />
          </Field>
          <datalist id="setup-fact-labels">
            {SUGGESTED.map((label) => (
              <option key={label} value={label} />
            ))}
          </datalist>
          <div className="row wide">
            <Button size="sm" disabled={pending}>
              Add the fact
            </Button>
          </div>
        </form>
      </section>
      <form
        key={`${noReply?.item_id}-${noReply?.days}`}
        className="stack"
        aria-labelledby="setup-reply"
        onSubmit={savePeriod}
      >
        <h3 id="setup-reply">When an application counts as unanswered</h3>
        <div>
          <Field
            className="short"
            label="No reply after (days)"
            hint={
              noReply?.source === "policy"
                ? "From the No reply rule of your policy."
                : `Not set: ${noReply?.days ?? 30} days until you choose.`
            }
          >
            <input
              name="days"
              type="number"
              min={1}
              max={3650}
              required
              defaultValue={noReply?.days ?? 30}
            />
          </Field>
        </div>
        <div className="row">
          <Button size="sm" disabled={pending}>
            Save the period
          </Button>
          <a className="btn quiet sm" href="#policy">
            The whole policy
          </a>
        </div>
      </form>
    </div>
  );
}
