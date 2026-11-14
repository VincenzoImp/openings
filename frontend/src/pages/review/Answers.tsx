import { useState, type FormEvent } from "react";
import {
  api,
  copyText,
  version,
  type Application,
  type Question,
} from "../../api";
import {
  Button,
  EmptyState,
  Field,
  StatementList,
  Statement,
  Tag,
} from "../../design";
import { ConfirmDialog } from "../../library/common";
import { useWorkspace } from "../../state";
import { QuestionDialog } from "./QuestionDialog";

/** The value a form control holds for an answer: "" when there is none. */
const shown = (value: unknown) =>
  value === undefined || value === null ? "" : String(value);
const answered = (value: unknown) =>
  value !== undefined && value !== null && value !== "";

/** The answer a control's text stands for, by the question's type; undefined when empty. */
function parse(question: Question, raw: string) {
  if (raw === "") return undefined;
  if (question.type === "boolean") return raw === "true";
  if (question.type === "number") return Number(raw);
  return raw;
}

/** The control of one answer, by the question's type; called, so Field labels it. */
function control(question: Question, value: unknown) {
  const text = shown(value);
  if (question.type === "choice" || question.options?.length)
    return (
      <select name={question.id} defaultValue={text}>
        <option value="">No answer yet</option>
        {question.options?.map((option) => (
          <option key={option}>{option}</option>
        ))}
      </select>
    );
  if (question.type === "boolean")
    return (
      <select name={question.id} defaultValue={text}>
        <option value="">No answer yet</option>
        <option value="true">Yes</option>
        <option value="false">No</option>
      </select>
    );
  if (question.type === "number")
    return (
      <input type="number" step="any" name={question.id} defaultValue={text} />
    );
  return (
    <textarea
      name={question.id}
      rows={3}
      defaultValue={text}
      maxLength={question.max_length}
    />
  );
}

/**
 * The questions of the employer's form with the live answers, one control
 * per question, and the questions themselves: add, edit, remove.
 */
export function Answers({ application }: { application: Application }) {
  const { mutate, pending, notify } = useWorkspace();
  const [editing, setEditing] = useState<Question | "new" | null>(null);
  const [removing, setRemoving] = useState<Question | null>(null);
  const questions = application.questions || [];
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const answers: Record<string, unknown> = {};
    for (const question of questions) {
      const value = parse(question, String(form.get(question.id) ?? ""));
      if (value !== undefined) answers[question.id] = value;
    }
    await mutate(
      () =>
        api(
          `/applications/${application.id}`,
          "PATCH",
          version(application, { answers }),
        ),
      "Answers saved.",
    );
  }
  const copyAll = () =>
    copyText(
      questions
        .map(
          (question) =>
            `${question.label}\n${shown(application.answers?.[question.id])}`,
        )
        .join("\n\n"),
    )
      .then(() => notify("Questions and answers copied."))
      .catch((cause) => notify(String(cause), true));
  return (
    <div className="stack">
      {questions.length ? (
        <form key={application.version} className="stack" onSubmit={save}>
          {questions.map((question) => {
            const value = application.answers?.[question.id];
            return (
              <div key={question.id} className="stack answer-field">
                <div className="row">
                  {question.required && <Tag>Required</Tag>}
                  {answered(value) ? (
                    <Tag tone="ready">Answered</Tag>
                  ) : (
                    <Tag tone="attention">Empty</Tag>
                  )}
                </div>
                <Field
                  label={question.label}
                  hint={
                    question.max_length
                      ? `At most ${question.max_length} characters.`
                      : undefined
                  }
                >
                  {control(question, value)}
                </Field>
              </div>
            );
          })}
          <div className="row">
            <Button variant="primary" size="sm" disabled={pending}>
              Save answers
            </Button>
            <Button type="button" variant="quiet" size="sm" onClick={copyAll}>
              Copy all
            </Button>
          </div>
        </form>
      ) : (
        <EmptyState title="No form questions">
          Add the questions of the employer's application form. Your agent
          drafts the answers from your record.
        </EmptyState>
      )}
      <section aria-label="Questions of the form" className="stack">
        <div className="spread">
          <h3>Questions of the form</h3>
          <Button size="sm" icon="plus" onClick={() => setEditing("new")}>
            Add question
          </Button>
        </div>
        {questions.length > 0 && (
          <StatementList label="Questions of the form">
            {questions.map((question) => (
              <Statement
                key={question.id}
                name={question.label}
                movable={false}
                label={question.label}
                caption={`${{ text: "Text", choice: "One of a list", boolean: "Yes or no", number: "Number" }[question.type || "text"] || "Text"}${question.required ? " · required" : ""}`}
                actions={
                  <>
                    <Button
                      size="sm"
                      variant="quiet"
                      onClick={() => setEditing(question)}
                    >
                      Edit<span className="sr"> {question.label}</span>
                    </Button>
                    <Button
                      size="sm"
                      variant="quiet danger"
                      onClick={() => setRemoving(question)}
                    >
                      Remove<span className="sr"> {question.label}</span>
                    </Button>
                  </>
                }
              />
            ))}
          </StatementList>
        )}
      </section>
      {editing && (
        <QuestionDialog
          application={application}
          question={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
      {removing && (
        <ConfirmDialog
          title="Remove this question and its answer?"
          confirm="Remove question and answer"
          keep="Keep question"
          onClose={() => setRemoving(null)}
          onConfirm={async () => {
            const answers = { ...application.answers };
            delete answers[removing.id];
            if (
              await mutate(
                () =>
                  api(
                    `/applications/${application.id}`,
                    "PATCH",
                    version(application, {
                      questions: questions.filter(
                        (item) => item.id !== removing.id,
                      ),
                      answers,
                    }),
                  ),
                "Question removed.",
              )
            )
              setRemoving(null);
          }}
        >
          <p>
            <strong>{removing.label}</strong> and its saved answer are removed.
            Document revisions keep their copies.
          </p>
        </ConfirmDialog>
      )}
    </div>
  );
}
