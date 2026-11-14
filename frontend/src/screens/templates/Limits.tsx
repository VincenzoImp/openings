import { useEffect, useState } from "react";
import {
  Field,
  Input,
  EMPTY,
  Properties,
  ReadEdit,
  formatNumber,
  useToast,
} from "../../ui";
import { ConflictNotice } from "../../query/ConflictNotice";
import { isConflict } from "../../query/mutation";
import { useUpdateTemplate, type Template } from "../../query/templates";
import {
  LIMITS,
  limitError,
  limitOf,
  limitText,
  otherRules,
  withLimits,
  type LimitKey,
} from "./model";

type Draft = Record<LimitKey, string>;

const draftOf = (template: Template): Draft =>
  Object.fromEntries(
    LIMITS.map(({ key }) => [key, String(limitOf(template.rules, key) ?? "")]),
  ) as Draft;

/** Pages, bullets per entry and bullet length: read first, Edit on purpose. */
export function LimitsTab({
  template,
  onDirty,
}: {
  template: Template;
  onDirty: (dirty: boolean) => void;
}) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [errors, setErrors] = useState<Partial<Record<LimitKey, string>>>({});
  const toast = useToast();
  const update = useUpdateTemplate(template, () => setDraft(null));
  const stored = draftOf(template);
  const changes = draft
    ? LIMITS.filter(({ key }) => draft[key].trim() !== stored[key]).length
    : 0;
  useEffect(() => onDirty(changes > 0), [changes, onDirty]);
  useEffect(() => () => onDirty(false), [onDirty]);
  const others = otherRules(template.rules);
  const save = () => {
    if (!draft) return;
    const found: Partial<Record<LimitKey, string>> = {};
    for (const { key, max } of LIMITS) {
      const error = limitError(draft[key], max);
      if (error) found[key] = error;
    }
    setErrors(found);
    if (Object.keys(found).length) {
      requestAnimationFrame(() =>
        document
          .querySelector<HTMLElement>(".tpl-limits [aria-invalid='true']")
          ?.focus(),
      );
      return;
    }
    update.mutate(
      { rules: withLimits(template.rules, draft) },
      {
        onSuccess: () => {
          setDraft(null);
          toast.show({ tone: "success", message: "Limits saved" });
        },
        onError: (cause) => {
          if (!isConflict(cause))
            toast.show({
              tone: "error",
              message: cause instanceof Error ? cause.message : "Not saved.",
            });
        },
      },
    );
  };
  return (
    <div className="tpl-limits">
      {update.conflict && (
        <ConflictNotice
          onReload={() => void update.reload()}
          onKeepEditing={() => void update.keepEditing()}
        />
      )}
      <ReadEdit
        title="Limits"
        editing={draft !== null}
        onEdit={() => {
          setErrors({});
          setDraft(draftOf(template));
        }}
        changes={changes}
        saving={update.isPending}
        onSave={save}
        onDiscard={() => {
          setDraft(null);
          setErrors({});
        }}
        read={
          <Properties
            items={LIMITS.map(({ key, label, unit }) => ({
              label,
              value: limitText(limitOf(template.rules, key), unit) ?? (
                <span className="tpl-none">No limit</span>
              ),
            }))}
          />
        }
        form={LIMITS.map(({ key, label, unit, max }) => (
          <Field
            key={key}
            label={label}
            hint={`In ${unit}, up to ${formatNumber(max)}. Empty: no limit.`}
            error={errors[key]}
            className="ui-field-full"
          >
            <Input
              type="number"
              inputMode="numeric"
              min={1}
              max={max}
              value={draft?.[key] ?? ""}
              onChange={(event) =>
                setDraft((current) =>
                  current ? { ...current, [key]: event.target.value } : current,
                )
              }
            />
          </Field>
        ))}
      />
      {others.length > 0 && (
        <section className="tpl-others" aria-label="Other settings">
          <h3>Other settings</h3>
          <Properties
            items={others.map((rule) => ({
              label: rule.label,
              value: rule.value || EMPTY,
            }))}
          />
          <p className="tpl-guidance-note">Written through the API.</p>
        </section>
      )}
    </div>
  );
}
