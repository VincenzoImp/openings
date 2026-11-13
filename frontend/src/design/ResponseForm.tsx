import { useEffect, useRef, type FormEvent, type ReactNode } from "react";
import { Button } from "./Button";
import { cx } from "./classes";
import { SegmentedControl } from "./Tabs";

/**
 * Record what an employer answered: one choice of a few kinds, the day it
 * arrived and an optional note. The button names what saving does ("Save and
 * close as rejected"); the caption says what follows from it.
 */
export function ResponseForm({
  label,
  question,
  options,
  choice,
  onChoice,
  date,
  onDate,
  dateLabel = "Date of the answer",
  note,
  onNote,
  withNote = true,
  latest,
  submit,
  caption,
  busy = false,
  stacked = false,
  onSubmit,
  onCancel,
}: {
  /** The accessible name of the form: "Record the employer's response for …". */
  label: string;
  /** "What did Willow Finance answer?" */
  question: string;
  options: { id: string; label: string }[];
  choice: string;
  onChoice: (id: string) => void;
  date: string;
  onDate: (date: string) => void;
  dateLabel?: string;
  note: string;
  onNote: (note: string) => void;
  /** False when what is recorded has no note. */
  withNote?: boolean;
  /** The latest day the date may be: today. */
  latest: string;
  submit: string;
  caption?: ReactNode;
  busy?: boolean;
  /**
   * One field under the other, the note full width and the buttons at the
   * end, right-aligned: the layout of a dialog. Otherwise one row in a list.
   */
  stacked?: boolean;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const form = useRef<HTMLFormElement>(null);
  // Opened from a button, the form takes focus on its current choice.
  useEffect(() => {
    form.current
      ?.querySelector<HTMLElement>("[aria-pressed=true]")
      ?.focus({ preventScroll: false });
  }, []);
  return (
    <form
      ref={form}
      className={cx("respond", stacked && "stacked")}
      aria-label={label}
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <fieldset>
        <legend>{question}</legend>
        <SegmentedControl
          label={question}
          value={choice}
          onChange={onChoice}
          options={options}
        />
      </fieldset>
      <label className="field">
        <span>{dateLabel}</span>
        <input
          type="date"
          required
          value={date}
          max={latest}
          onChange={(event) => onDate(event.target.value)}
        />
      </label>
      {withNote ? (
        <label className="field">
          <span>
            Note <span className="hint">optional</span>
          </span>
          {stacked ? (
            <textarea
              rows={3}
              maxLength={2000}
              value={note}
              onChange={(event) => onNote(event.target.value)}
            />
          ) : (
            <input
              type="text"
              maxLength={2000}
              value={note}
              onChange={(event) => onNote(event.target.value)}
            />
          )}
        </label>
      ) : (
        !stacked && <span />
      )}
      {stacked && caption && (
        <p className="caption respond-caption">{caption}</p>
      )}
      {stacked ? (
        <div className="respond-foot">
          <Button type="button" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" loading={busy}>
            {submit}
          </Button>
        </div>
      ) : (
        <div className="row">
          <Button variant="primary" size="sm" type="submit" loading={busy}>
            {submit}
          </Button>
          <Button variant="quiet" size="sm" type="button" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      )}
      {!stacked && caption && (
        <p className="caption respond-caption">{caption}</p>
      )}
    </form>
  );
}
