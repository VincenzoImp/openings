import { useEffect, useId, useRef, useState } from "react";
import { ArrowRight, EyeOff, Pencil, Plus, X } from "lucide-react";
import { Button, Tag, Select, Icon, useToast } from "../../ui";
import { isConflict } from "../../query/mutation";
import {
  useSaveSettings,
  useUnspokenNewJobs,
  type Settings,
} from "../../query/preferences";
import { LANGUAGES, hiddenLine, languageName, replyDays } from "./model";

/** Say what failed in a settings write; a conflict has already reloaded. */
function useFailure() {
  const toast = useToast();
  return (cause: unknown) =>
    toast.show({
      tone: "error",
      message: isConflict(cause)
        ? "Changed elsewhere. The latest settings are shown; try again."
        : cause instanceof Error
          ? cause.message
          : "The change was not saved.",
    });
}

/**
 * Languages I speak, under Facts about me: chips at rest, and the link to the
 * Jobs filter that hides postings requiring another language.
 */
export function Languages({ settings }: { settings: Settings }) {
  const id = useId();
  const [editing, setEditing] = useState(false);
  const save = useSaveSettings();
  const fail = useFailure();
  const spoken = settings.spoken_languages;
  const effect = useUnspokenNewJobs(spoken.length > 0);
  const others = Object.keys(LANGUAGES).filter(
    (code) => !spoken.includes(code),
  );
  const edit = useRef<HTMLButtonElement>(null);
  const wasEditing = useRef(false);
  useEffect(() => {
    if (wasEditing.current && !editing) edit.current?.focus();
    wasEditing.current = editing;
  }, [editing]);
  const change = (languages: string[]) =>
    save.mutate(
      { expected_version: settings.version, spoken_languages: languages },
      { onError: fail },
    );
  return (
    <div className="pref-sub" role="group" aria-labelledby={`${id}-title`}>
      <div className="pref-subhead">
        <h3 id={`${id}-title`}>Languages I speak</h3>
        {!editing && (
          <Button
            ref={edit}
            variant="ghost"
            size="sm"
            icon={spoken.length ? Pencil : Plus}
            aria-label={spoken.length ? "Edit languages" : "Add a language"}
            onClick={() => setEditing(true)}
          >
            {spoken.length ? "Edit" : "Add"}
          </Button>
        )}
      </div>
      {editing ? (
        <div className="pref-langs-edit">
          {spoken.length > 0 && (
            <ul className="pref-chips" aria-label="Languages I speak">
              {spoken.map((code) => (
                <li key={code}>
                  <span className="pref-chip">
                    {languageName(code)}
                    <button
                      type="button"
                      aria-label={`Remove ${languageName(code)}`}
                      disabled={save.isPending}
                      onClick={() =>
                        change(spoken.filter((other) => other !== code))
                      }
                    >
                      <Icon icon={X} size="sm" />
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <div className="pref-langs-add">
            <Select
              aria-label="Add a language"
              value=""
              disabled={save.isPending}
              onChange={(event) => {
                if (event.target.value) change([...spoken, event.target.value]);
              }}
            >
              <option value="">Add a language…</option>
              {others.map((code) => (
                <option key={code} value={code}>
                  {languageName(code)}
                </option>
              ))}
            </Select>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setEditing(false)}
            >
              Done
            </Button>
          </div>
        </div>
      ) : spoken.length ? (
        <p className="pref-langs">
          {spoken.map((code) => (
            <Tag key={code}>{languageName(code)}</Tag>
          ))}
        </p>
      ) : (
        <p className="pref-muted">
          None yet. With your languages listed, Jobs can hide postings that
          require another one.
        </p>
      )}
      {spoken.length > 0 && (
        <a className="pref-filter" href="#jobs?hide_unspoken=true">
          <Icon icon={EyeOff} />
          <span className="pref-filter-text">
            <span className="pref-filter-label">
              Hide new jobs that require another language
            </span>
            <span className="pref-filter-note">
              A filter in Jobs
              {effect ? ` · ${hiddenLine(effect.hidden, effect.total)}` : ""}
            </span>
          </span>
          <Icon icon={ArrowRight} className="pref-filter-go" />
        </a>
      )}
    </div>
  );
}

/** Following up: "Count an application as no reply after [45] days." */
export function FollowingUp({ settings }: { settings: Settings }) {
  const id = useId();
  const [draft, setDraft] = useState<string | null>(null);
  const [invalid, setInvalid] = useState(false);
  const save = useSaveSettings();
  const fail = useFailure();
  const toast = useToast();
  const trigger = useRef<HTMLButtonElement>(null);
  const field = useRef<HTMLInputElement>(null);
  const open = draft !== null;
  useEffect(() => {
    if (open) field.current?.select();
  }, [open]);
  const close = () => {
    setDraft(null);
    setInvalid(false);
    requestAnimationFrame(() => trigger.current?.focus());
  };
  const submit = () => {
    const days = replyDays(draft ?? "");
    if (!days) return setInvalid(true);
    if (days === settings.no_reply_days) return close();
    save.mutate(
      { expected_version: settings.version, no_reply_days: days },
      {
        onSuccess: () => {
          close();
          toast.show({
            tone: "success",
            message: `Applications count as no reply after ${days} days.`,
          });
        },
        onError: fail,
      },
    );
  };
  return (
    <section className="pref-section" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`} className="pref-title">
        Following up
      </h2>
      {draft === null ? (
        <p className="pref-sentence">
          Count an application as <em>no reply</em> after{" "}
          <button
            ref={trigger}
            type="button"
            className="pref-days"
            aria-label={`No-reply period: ${settings.no_reply_days} days. Change`}
            onClick={() => setDraft(String(settings.no_reply_days))}
          >
            {settings.no_reply_days} days
          </button>
          .
        </p>
      ) : (
        <form
          className="pref-sentence pref-days-form"
          data-unguarded=""
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <label htmlFor={`${id}-days`}>
            Count an application as <em>no reply</em> after
          </label>{" "}
          <input
            ref={field}
            id={`${id}-days`}
            className="ui-input pref-days-input"
            type="number"
            inputMode="numeric"
            min={1}
            max={365}
            value={draft}
            aria-invalid={invalid || undefined}
            aria-describedby={invalid ? `${id}-error` : undefined}
            onChange={(event) => {
              setDraft(event.target.value);
              setInvalid(false);
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                event.stopPropagation();
                close();
              }
            }}
          />{" "}
          days.
          <span className="pref-days-actions">
            <Button variant="ghost" size="sm" onClick={close}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              type="submit"
              disabled={save.isPending}
            >
              Save
            </Button>
          </span>
          {invalid && (
            <span className="pref-error" id={`${id}-error`}>
              Give a whole number of days from 1 to 365.
            </span>
          )}
        </form>
      )}
    </section>
  );
}
