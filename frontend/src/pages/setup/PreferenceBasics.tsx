import type { FormEvent } from "react";
import {
  api,
  type NoReply,
  type PreferenceSectionName,
  type Preferences,
} from "../../api";
import { Button, Field } from "../../design";
import { useWorkspace } from "../../state";
import { replyDays } from "../preferences/model";

const ASKED: {
  section: PreferenceSectionName;
  hint: string;
  placeholder: string;
}[] = [
  {
    section: "looking_for",
    hint: "Roles, places and conditions that make a job worth a look.",
    placeholder: "Backend roles, remote within Europe.",
  },
  {
    section: "ruled_out",
    hint: "What makes a job not worth applying to.",
    placeholder: "Agencies that hire for clients.",
  },
];

/**
 * What a new workspace needs first from Preferences: what the owner looks for,
 * what they rule out and the no-reply period. Preferences has every section.
 */
export function PreferenceBasics({
  preferences,
  noReply,
}: {
  preferences: Preferences;
  noReply: NoReply | null;
}) {
  const { mutate, pending, notify } = useWorkspace();
  const sectionOf = (name: PreferenceSectionName) =>
    preferences.sections.find((item) => item.section === name);
  async function add(
    name: PreferenceSectionName,
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    const form = event.currentTarget;
    const text = String(new FormData(form).get("text") || "").trim();
    const section = sectionOf(name);
    if (!text || !section) return notify("Write the statement.", true);
    if (
      await mutate(
        () =>
          api(`/preferences/${name}`, "PUT", {
            expected_version: section.version,
            items: [...section.items, { text }],
          }),
        `Added to ${section.title}.`,
      )
    )
      form.reset();
  }
  async function savePeriod(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const days = replyDays(
      String(new FormData(event.currentTarget).get("days")),
    );
    if (!days) return notify("Give a number of days from 1 to 365.", true);
    await mutate(
      () =>
        api("/settings", "PATCH", {
          expected_version: preferences.settings.version,
          no_reply_days: days,
        }),
      `Applications without an answer after ${days} days count as no reply.`,
    );
  }
  return (
    <div className="stack">
      {ASKED.map(({ section: name, hint, placeholder }) => {
        const section = sectionOf(name);
        if (!section) return null;
        return (
          <section
            key={name}
            className="stack"
            aria-labelledby={`setup-${name}`}
          >
            <h3 id={`setup-${name}`}>{section.title}</h3>
            {section.items.length ? (
              <ul className="plain" aria-label={section.title}>
                {section.items.map((item, index) => (
                  <li key={index}>{item.text}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">Nothing yet. {hint}</p>
            )}
            <form
              className="form-grid"
              aria-label={`Add to ${section.title}`}
              onSubmit={(event) => add(name, event)}
            >
              <Field label="Statement" className="wide">
                <textarea
                  name="text"
                  rows={2}
                  maxLength={2000}
                  required
                  placeholder={placeholder}
                />
              </Field>
              <div className="row wide">
                <Button size="sm" disabled={pending}>
                  Add
                </Button>
              </div>
            </form>
          </section>
        );
      })}
      <form
        key={`${preferences.settings.version}-${preferences.settings.no_reply_days}`}
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
              noReply?.source === "settings"
                ? "Set in Preferences, Facts about me."
                : `Not set: ${preferences.settings.no_reply_days} days until you choose.`
            }
          >
            <input
              name="days"
              type="number"
              min={1}
              max={365}
              required
              defaultValue={preferences.settings.no_reply_days}
            />
          </Field>
        </div>
        <div className="row">
          <Button size="sm" disabled={pending}>
            Save the period
          </Button>
          <a className="btn quiet sm" href="#preferences">
            All your preferences
          </a>
        </div>
      </form>
    </div>
  );
}
