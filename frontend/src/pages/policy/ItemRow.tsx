import {
  date,
  policySections,
  type PolicyItem,
  type PolicySectionName,
  type PolicySignal,
} from "../../api";
import {
  ActorChip,
  Button,
  StatementValue,
  Switch,
  Tag,
  ValueTree,
} from "../../design";
import { describe } from "../../design/kv";
import { ruleText, scopeLabels, valueText } from "./model";
import { RuleMatches } from "./RuleMatches";

/** The tags beside an item's label: scope, signal and what is not confirmed. */
export function ItemTags({
  item,
  signals,
}: {
  item: PolicyItem;
  signals: PolicySignal[];
}) {
  const signal = signals.find((entry) => entry.signal === item.rule?.signal);
  return (
    <>
      {item.scope && <Tag>{scopeLabels[item.scope]}</Tag>}
      {item.rule && (
        <Tag tone="info">
          Uses a signal: {(signal?.label || item.rule.signal).toLowerCase()}
        </Tag>
      )}
      {!item.confirmed &&
        (item.origin ? (
          <Tag tone="attention">Unsorted</Tag>
        ) : (
          <Tag tone="agent">Proposed</Tag>
        ))}
    </>
  );
}

/** Statement, value, note and the rule's switch of one item. */
export function ItemBody({
  item,
  signals,
  signalsApplied,
  busy,
  onEnabled,
}: {
  item: PolicyItem;
  signals: PolicySignal[];
  signalsApplied: boolean;
  busy: boolean;
  onEnabled: (enabled: boolean) => void;
}) {
  const value = valueText(item);
  return (
    <>
      {item.statement && <div className="prose">{item.statement}</div>}
      {value !== null && <StatementValue>{value}</StatementValue>}
      {item.value_type === "structured" && (
        <details className="kv-tree value">
          <summary>Copied value: {describe(item.value).toLowerCase()}</summary>
          <ValueTree value={item.value} />
        </details>
      )}
      {item.note && <div className="muted">Note: {item.note}</div>}
      {item.rule && (
        <div className="rule-state">
          <Switch
            label={`Apply ${item.label} automatically`}
            checked={item.enabled}
            disabled={busy}
            onChange={onEnabled}
          >
            Applied automatically: {item.enabled ? "on" : "off"}
          </Switch>
          <span className="muted">
            {ruleText(item.rule, signals)}.
            {!signalsApplied &&
              " Signals arrive in a later release: until then the rule is stored and nothing is dismissed."}
          </span>
          {signalsApplied && <RuleMatches item={item} />}
        </div>
      )}
    </>
  );
}

/** When the item was confirmed and by whom, or why it is not. */
export function ItemCaption({ item }: { item: PolicyItem }) {
  if (item.confirmed) {
    const proposed =
      item.created_by?.kind === "token" &&
      item.created_by.token_kind === "agent";
    return (
      <>
        Confirmed {date(item.confirmed_at || undefined)} ·{" "}
        {proposed ? (
          <>
            proposed by <ActorChip actor={item.created_by} />, confirmed by{" "}
            <ActorChip actor={item.confirmed_by} />
          </>
        ) : (
          <>
            last changed by <ActorChip actor={item.updated_by} />
          </>
        )}
      </>
    );
  }
  if (item.origin)
    return (
      <>
        {item.origin.note} (<span className="mono">{item.origin.key}</span>).
        Not confirmed, so the agent does not rely on it.
      </>
    );
  return (
    <>
      Proposed {date(item.created_at)} by <ActorChip actor={item.updated_by} />{" "}
      · not confirmed.
      {item.rule && " A rule stays off until you turn it on."}
    </>
  );
}

/** Choose another section for an item. */
export function MoveSelect({
  item,
  disabled,
  onMove,
}: {
  item: PolicyItem;
  disabled: boolean;
  onMove: (section: PolicySectionName) => void;
}) {
  return (
    <label>
      <span className="sr">Move {item.label} to a section</span>
      <select
        className="input move"
        value=""
        disabled={disabled || !!item.rule}
        onChange={(event) => {
          if (event.target.value)
            onMove(event.target.value as PolicySectionName);
        }}
      >
        <option value="">Move to…</option>
        {Object.entries(policySections)
          .filter(([name]) => name !== item.section)
          .map(([name, label]) => (
            <option key={name} value={name}>
              {label}
            </option>
          ))}
      </select>
    </label>
  );
}

/** Confirm and sort a proposal or a copied value. */
export function Unconfirmed({
  item,
  busy,
  onConfirm,
  onMove,
}: {
  item: PolicyItem;
  busy: boolean;
  onConfirm: () => void;
  onMove: (section: PolicySectionName) => void;
}) {
  const words =
    item.section === "facts" || item.section === "eligibility"
      ? "Confirm as a fact"
      : "Confirm";
  return (
    <div className="row rule-state">
      <Button
        size="sm"
        disabled={busy}
        aria-label={`${words}: ${item.label}`}
        onClick={onConfirm}
      >
        {words}
      </Button>
      {!item.rule && <MoveSelect item={item} disabled={busy} onMove={onMove} />}
    </div>
  );
}
