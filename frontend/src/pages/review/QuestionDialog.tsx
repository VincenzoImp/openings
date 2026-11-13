import { useState, type FormEvent } from "react";
import {
  ApiError,
  api,
  newId,
  version,
  type Application,
  type Question,
} from "../../api";
import { Banner, Button, Dialog, Field } from "../../design";
import { useWorkspace } from "../../state";

const TYPES: Record<string, string> = {
  text: "Text",
  choice: "One of a list",
  boolean: "Yes or no",
  number: "Number",
};

/**
 * Add or edit one question of the employer's form. An answer that no longer
 * fits the edited question is kept unless the owner chooses to clear it.
 */
export function QuestionDialog({
  application,
  question,
  onClose,
}: {
  application: Application;
  question: Question | null;
  onClose: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  const [kind, setKind] = useState(question?.type || "text");
  const [incompatible, setIncompatible] = useState("");
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const edited: Question = {
      id: question?.id || newId().replace(/-/g, "").slice(0, 16),
      label: String(form.get("label") || "").trim(),
      type: kind,
      required: form.get("required") === "on",
      options:
        kind === "choice"
          ? String(form.get("options") || "")
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean)
          : [],
      ...(kind === "text" && Number(form.get("max_length"))
        ? { max_length: Number(form.get("max_length")) }
        : {}),
    };
    const questions = question
      ? application.questions.map((item) =>
          item.id === question.id ? edited : item,
        )
      : [...application.questions, edited];
    const clear = question && form.get("clear") === "on";
    const answers = { ...application.answers };
    if (clear) delete answers[question.id];
    const ok = await mutate(async () => {
      try {
        await api(
          `/applications/${application.id}`,
          "PATCH",
          version(application, { questions, ...(clear ? { answers } : {}) }),
        );
      } catch (error) {
        if (
          error instanceof ApiError &&
          error.status === 422 &&
          error.code.startsWith("answer_")
        )
          setIncompatible(error.message);
        throw error;
      }
    }, "Question saved.");
    if (ok) onClose();
  }
  return (
    <Dialog
      title={question ? "Edit the question" : "Add a question"}
      onClose={onClose}
    >
      <form className="stack" onSubmit={save}>
        <Field label="Question">
          <textarea
            name="label"
            rows={3}
            required
            maxLength={2000}
            defaultValue={question?.label}
          />
        </Field>
        <Field label="Answer">
          <select
            value={kind}
            onChange={(event) => setKind(event.target.value)}
          >
            {Object.entries(TYPES).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        {kind === "choice" && (
          <Field label="Choices" hint="One choice per line.">
            <textarea
              name="options"
              rows={4}
              required
              defaultValue={question?.options?.join("\n")}
            />
          </Field>
        )}
        {kind === "text" && (
          <Field label="Character limit" hint="Optional.">
            <input
              type="number"
              name="max_length"
              min={1}
              max={50000}
              defaultValue={question?.max_length}
            />
          </Field>
        )}
        <label className="toggle">
          <input
            type="checkbox"
            name="required"
            defaultChecked={question?.required}
          />
          <span>An answer is required</span>
        </label>
        {incompatible && (
          <Banner tone="attention" title="The saved answer does not fit">
            <p>{incompatible}</p>
            <label className="toggle">
              <input type="checkbox" name="clear" />
              <span>Clear the saved answer when saving the question</span>
            </label>
          </Banner>
        )}
        <div className="row">
          <Button variant="primary" disabled={pending}>
            Save the question
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
