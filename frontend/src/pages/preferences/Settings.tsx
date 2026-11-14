import { useState, type FormEvent } from "react";
import type { WorkspaceSettings } from "../../api";
import { Button, Icon } from "../../design";
import { useWorkspace } from "../../state";
import { LANGUAGES, languageName } from "../../screens/jobs/model";
import type { Outcome } from "./Section";
import { replyDays } from "./model";

/** Change the settings; the screen applies the answer, or reads them again. */
export type SaveSettings = (
  patch: { no_reply_days?: number; spoken_languages?: string[] },
  message: string,
) => Promise<Outcome>;

/**
 * The two settings under Facts about me: the languages the owner speaks (the
 * Jobs filter hides postings requiring another one) and the no-reply period.
 */
export function FactSettings({
  settings,
  busy,
  save,
}: {
  settings: WorkspaceSettings;
  busy: boolean;
  save: SaveSettings;
}) {
  const { notify } = useWorkspace();
  const [adding, setAdding] = useState("");
  const spoken = settings.spoken_languages;
  const others = Object.keys(LANGUAGES).filter(
    (code) => !spoken.includes(code),
  );
  async function addLanguage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!adding) return notify("Choose a language.", true);
    if (
      (await save({ spoken_languages: [...spoken, adding] }, "Saved.")) === "ok"
    )
      setAdding("");
  }
  async function savePeriod(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const days = replyDays(
      String(new FormData(event.currentTarget).get("days")),
    );
    if (!days) return notify("Give a number of days from 1 to 365.", true);
    await save(
      { no_reply_days: days },
      `Applications without an answer after ${days} days count as no reply.`,
    );
  }
  return (
    <>
      <div className="sub stack">
        <h3 id="preferences-languages">Languages I speak</h3>
        {spoken.length ? (
          <ul className="chips" aria-labelledby="preferences-languages">
            {spoken.map((code) => (
              <li key={code}>
                <button
                  type="button"
                  className="chip"
                  aria-label={`Remove ${languageName(code)}`}
                  disabled={busy}
                  onClick={() =>
                    save(
                      {
                        spoken_languages: spoken.filter(
                          (other) => other !== code,
                        ),
                      },
                      `${languageName(code)} removed.`,
                    )
                  }
                >
                  {languageName(code)}
                  <Icon name="close" />
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">
            No language yet. Jobs can hide postings that require a language you
            do not speak once you list yours.
          </p>
        )}
        <form
          className="row"
          aria-label="Add a language"
          onSubmit={addLanguage}
        >
          <label>
            <span className="sr">Language</span>
            <select
              className="input"
              value={adding}
              onChange={(event) => setAdding(event.target.value)}
            >
              <option value="">Choose a language</option>
              {others.map((code) => (
                <option key={code} value={code}>
                  {languageName(code)}
                </option>
              ))}
            </select>
          </label>
          <Button size="sm" icon="plus" disabled={busy}>
            Add language
          </Button>
        </form>
      </div>
      <form
        key={`${settings.version}-${settings.no_reply_days}`}
        className="sub stack"
        aria-labelledby="preferences-following-up"
        onSubmit={savePeriod}
      >
        <h3 id="preferences-following-up">Following up</h3>
        <div className="row">
          <label htmlFor="preferences-reply-days">
            Count an application as no reply after
          </label>
          <input
            id="preferences-reply-days"
            className="input days"
            name="days"
            type="number"
            min={1}
            max={365}
            required
            defaultValue={settings.no_reply_days}
          />
          <span>days</span>
          <Button size="sm" disabled={busy}>
            Save
          </Button>
        </div>
      </form>
    </>
  );
}
