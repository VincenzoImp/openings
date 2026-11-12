import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Button } from "./Button";

/**
 * Something the owner is asked: who asks and when, the question, why it
 * matters, what it is about, and the controls or the answer as children.
 */
export function Question({
  ask,
  why,
  lead,
  time,
  about,
  small = false,
  children,
}: {
  ask: string;
  why?: ReactNode;
  /** Above the question: the actor chip of who asks, or a tag. */
  lead?: ReactNode;
  time?: string;
  /** Links to the records the question is about. */
  about?: ReactNode;
  /** A settled question: the text is not a heading-sized line. */
  small?: boolean;
  children?: ReactNode;
}) {
  return (
    <article className="question" aria-label={ask}>
      {(lead || time) && (
        <div className="spread">
          {lead}
          {time && <span className="caption nowrap">{time}</span>}
        </div>
      )}
      <p className={small ? "asked" : "ask"}>{ask}</p>
      {why && <p className="why prose">{why}</p>}
      {about && <p className="caption about">{about}</p>}
      {children}
    </article>
  );
}

/**
 * The controls that answer a question. A choice answers at once; "Write an
 * answer" opens a text box, and a choice picked while it holds text sends
 * both. "Not now" only closes the box: the question stays open.
 */
export function AnswerControls({
  choices = [],
  initialText = "",
  open: startOpen = false,
  busy = false,
  submitLabel = "Answer",
  placeholder = "Your answer",
  onAnswer,
  extra,
}: {
  choices?: string[];
  initialText?: string;
  /** Start with the text box open (a question without choices). */
  open?: boolean;
  busy?: boolean;
  submitLabel?: string;
  placeholder?: string;
  onAnswer: (answer: string, choice?: string) => void;
  /** Further quiet actions at the end of the row, such as Withdraw. */
  extra?: ReactNode;
}) {
  const id = useId();
  const [open, setOpen] = useState(startOpen);
  const [text, setText] = useState(initialText);
  const box = useRef<HTMLTextAreaElement>(null);
  const opener = useRef<HTMLButtonElement>(null);
  // Focus follows the box: into it when it opens, back to its button after.
  const moved = useRef(false);
  useEffect(() => {
    if (!moved.current) return;
    moved.current = false;
    (open ? box.current : opener.current)?.focus();
  }, [open]);
  const toggle = (next: boolean) => {
    moved.current = true;
    setOpen(next);
  };
  const written = text.trim();
  return (
    <div className="answer">
      {choices.length > 0 && (
        <div className="row">
          <div className="row" role="group" aria-label="Choices">
            {choices.map((choice) => (
              <Button
                key={choice}
                size="sm"
                disabled={busy}
                onClick={() => onAnswer(open ? written : "", choice)}
              >
                {choice}
              </Button>
            ))}
          </div>
          {!open && (
            <Button
              ref={opener}
              variant="quiet"
              size="sm"
              onClick={() => toggle(true)}
            >
              Write an answer
            </Button>
          )}
          {!open && extra}
        </div>
      )}
      {open ? (
        <form
          className="write"
          onSubmit={(event) => {
            event.preventDefault();
            if (written) onAnswer(written);
          }}
        >
          <label className="sr" htmlFor={id}>
            Your answer
          </label>
          <textarea
            ref={box}
            id={id}
            className="input"
            rows={3}
            maxLength={8000}
            placeholder={placeholder}
            value={text}
            aria-describedby={choices.length ? id + "-hint" : undefined}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") toggle(false);
              if (event.key === "Enter" && (event.metaKey || event.ctrlKey))
                event.currentTarget.form?.requestSubmit();
            }}
          />
          {choices.length > 0 && (
            <p className="caption" id={id + "-hint"}>
              Answer in your own words, or write a comment and pick a choice
              above to send both.
            </p>
          )}
          <div className="row">
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={busy || !written}
            >
              {submitLabel}
            </Button>
            <Button
              type="button"
              variant="quiet"
              size="sm"
              onClick={() => toggle(false)}
            >
              Not now
            </Button>
            {extra}
          </div>
        </form>
      ) : (
        !choices.length && (
          <div className="row">
            <Button ref={opener} size="sm" onClick={() => toggle(true)}>
              Write an answer
            </Button>
            {extra}
          </div>
        )
      )}
    </div>
  );
}
