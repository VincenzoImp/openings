import { api, formatTime, type ListResult } from "../../api";
import { Button, EmptyState, ErrorBanner, Loading, Tag } from "../../design";
import { useEditorRecord, useResource, useWorkspace } from "../../state";

export interface Provider {
  id: string;
  name: string;
  version: number;
  capability: { supported: boolean; kind: string; description: string };
  policy: { enabled: boolean; min_interval_seconds: number };
  runtime: {
    cooldown_until?: string;
    next_allowed_at?: string;
    last_error?: string;
    last_status?: number;
    requests_hour?: number;
    requests_day?: number;
  };
}
const NONE: ListResult<Provider> = { items: [], total: 0 };
const future = (value?: string) =>
  !!value && new Date(value).valueOf() > Date.now();

/** Where the shared request gate stands for one provider, as a tag. */
export function gateState(provider: Provider) {
  const { runtime, policy, capability } = provider;
  if (!capability.supported)
    return { text: "Not supported", tone: "neutral" as const, detail: "" };
  if (!policy.enabled)
    return { text: "Off", tone: "neutral" as const, detail: "" };
  if (future(runtime.cooldown_until))
    return {
      text: `Paused by the provider until ${formatTime(runtime.cooldown_until)}`,
      tone: "attention" as const,
      detail: "It asked for a pause; waiting tasks resume after it.",
    };
  if (future(runtime.next_allowed_at))
    return {
      text: "Spacing requests",
      tone: "info" as const,
      detail: `Next request ${formatTime(runtime.next_allowed_at)}`,
    };
  return { text: "Ready", tone: "ready" as const, detail: "" };
}

function ProviderRow({ provider: initial }: { provider: Provider }) {
  const provider = useEditorRecord(initial, `/providers/${initial.id}`)!;
  return <ProviderForm key={provider.version} provider={provider} />;
}

function ProviderForm({ provider }: { provider: Provider }) {
  const { mutate, pending } = useWorkspace();
  const state = gateState(provider);
  const { runtime } = provider;
  const supported = provider.capability.supported;
  return (
    <li>
      <form
        className="provider"
        aria-label={provider.name}
        onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          void mutate(
            () =>
              api(`/providers/${provider.id}`, "PATCH", {
                expected_version: provider.version,
                enabled: form.get("enabled") === "on",
                min_interval_seconds: Number(form.get("min_interval_seconds")),
              }),
            `${provider.name} request settings saved.`,
          );
        }}
      >
        <div className="grow">
          <span className="title">{provider.name}</span>{" "}
          <Tag tone={state.tone}>{state.text}</Tag>
          <div className="meta">
            {provider.capability.description} {state.detail}
          </div>
          <div className="meta num">
            {runtime.requests_hour || 0} requests in the last hour,{" "}
            {runtime.requests_day || 0} in 24 hours · last answer{" "}
            {runtime.last_status ? `HTTP ${runtime.last_status}` : "none yet"}
          </div>
          {runtime.last_error && (
            <div className="meta danger-text">{runtime.last_error}</div>
          )}
        </div>
        <label className="toggle">
          <input
            type="checkbox"
            role="switch"
            className="switch"
            name="enabled"
            defaultChecked={provider.policy.enabled}
            disabled={!supported}
          />
          On
        </label>
        <label className="spacing">
          <span className="sr">{provider.name}: </span>
          <input
            className="input"
            name="min_interval_seconds"
            type="number"
            required
            min={0}
            max={3600}
            step={0.1}
            disabled={!supported}
            defaultValue={provider.policy.min_interval_seconds}
          />
          <span>seconds between requests</span>
        </label>
        <Button size="sm" disabled={pending || !supported}>
          Save
        </Button>
      </form>
    </li>
  );
}

/**
 * The shared, persisted request gate: every request to a provider waits its
 * turn here, including previews, redirects and Run once.
 */
export function Providers() {
  const providers = useResource("/providers", NONE);
  return (
    <div className="stack">
      <p className="muted measure">
        Every request to a provider waits its turn here, including previews,
        redirects and Run once. Longer spacing is slower and safer; 5 seconds is
        the default and 0 turns spacing off. A pause a provider asks for (an
        answer of "too many requests") stays in effect when you save.
      </p>
      <section className="card" aria-label="Providers">
        {providers.error ? (
          <div className="body">
            <ErrorBanner message={providers.error} retry={providers.reload} />
          </div>
        ) : providers.loading ? (
          <Loading label="Loading providers…" />
        ) : providers.data.items.length ? (
          <ul className="list">
            {providers.data.items.map((provider) => (
              <ProviderRow key={provider.id} provider={provider} />
            ))}
          </ul>
        ) : (
          <EmptyState title="No provider">
            Providers appear when the workspace starts.
          </EmptyState>
        )}
        <footer>
          <span className="caption grow">
            Request counts are for information; the gate uses only the spacing
            and the pauses providers ask for.
          </span>
          <Button size="sm" variant="quiet" onClick={providers.reload}>
            Refresh
          </Button>
        </footer>
      </section>
    </div>
  );
}
