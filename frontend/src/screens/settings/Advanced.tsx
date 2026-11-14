import { useState } from "react";
import { isConflict } from "../../query/mutation";
import { invalidate } from "../../query/query";
import { formatNumber } from "../../ui/format";
import { Properties, SkeletonRows } from "../../ui/Page";
import { useToast } from "../../ui/Toast";
import { sitesInUse } from "../sources/model";
import { useSources } from "../sources/queries";
import { gateOf, spacing } from "./model";
import { useProviders, useUpdateProvider, useWorkspaceInfo } from "./queries";
import { SettingsGroup, SettingsSection } from "./Rows";

type Provider = {
  id: string;
  name: string;
  version: number;
  capability: Record<string, unknown>;
  policy: Record<string, unknown>;
  runtime: Record<string, unknown>;
};

/** Request limits of the job sites in use, and this workspace's version. */
export function Advanced() {
  const info = useWorkspaceInfo();
  return (
    <SettingsSection title="Advanced">
      <SettingsGroup title="Request limits per job site">
        <p className="set-row-desc">
          Every request to a job site waits its turn here, including tests and
          Check now. Longer spacing is slower and gentler. A change is saved
          when you leave the field.
        </p>
        <Limits />
      </SettingsGroup>
      <SettingsGroup title="This workspace">
        <Properties
          items={[
            { label: "Version", value: info.data?.version },
            {
              label: "Database schema",
              value:
                info.data?.schema_version != null
                  ? String(info.data.schema_version)
                  : "",
            },
            { label: "Address", value: info.data?.origin ?? "" },
          ]}
        />
      </SettingsGroup>
    </SettingsSection>
  );
}

function Limits() {
  const providers = useProviders();
  const sources = useSources();
  if (providers.isPending || sources.isPending)
    return <SkeletonRows rows={3} />;
  if (providers.isError || sources.isError)
    return (
      <p className="set-row-desc set-danger" role="alert">
        The request limits could not be read.
      </p>
    );
  const used = sitesInUse(sources.data);
  const rows = (providers.data as unknown as Provider[]).filter((provider) =>
    used.has(provider.id),
  );
  if (!rows.length)
    return (
      <p className="set-row-desc">
        No job site in use yet. Add a source to see its limits here.
      </p>
    );
  return (
    <div className="set-table-wrap">
      <table className="set-table">
        <caption className="ui-sr">
          Request limits of the job sites in use
        </caption>
        <thead>
          <tr>
            <th scope="col">Job site</th>
            <th scope="col">Status</th>
            <th scope="col" data-numeric="">
              Seconds between requests
            </th>
            <th scope="col" data-numeric="">
              Requests in 24 h
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((provider) => (
            <LimitRow key={provider.id} provider={provider} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LimitRow({ provider }: { provider: Provider }) {
  const update = useUpdateProvider();
  const toast = useToast();
  const stored = Number(provider.policy.min_interval_seconds ?? 0);
  const [value, setValue] = useState<string | null>(null);
  const [invalid, setInvalid] = useState(false);
  const gate = gateOf(provider);
  const shown = value ?? String(stored);
  function commit() {
    if (value == null) return;
    const seconds = spacing(value);
    if (seconds == null) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    if (seconds === stored) {
      setValue(null);
      return;
    }
    update.mutate(
      {
        id: provider.id,
        expected_version: provider.version,
        min_interval_seconds: seconds,
      },
      {
        onSuccess: () => {
          setValue(null);
          toast.show({
            message: `${provider.name}: ${formatNumber(seconds)} ${seconds === 1 ? "second" : "seconds"} between requests`,
            tone: "success",
          });
        },
        onError: (error) => {
          setValue(null);
          if (isConflict(error)) void invalidate(["providers"]);
          toast.show({
            message: isConflict(error)
              ? `${provider.name} was changed elsewhere; its current limit is shown.`
              : error.message,
            tone: "error",
          });
        },
      },
    );
  }
  return (
    <tr>
      <th scope="row">{provider.name}</th>
      <td>
        <span className="set-gate" data-tone={gate.tone}>
          <span className="set-gate-dot" aria-hidden="true" />
          {gate.text}
        </span>
      </td>
      <td data-numeric="">
        <input
          className="ui-input set-spacing"
          inputMode="decimal"
          aria-label={`Seconds between requests to ${provider.name}`}
          aria-invalid={invalid || undefined}
          aria-describedby={
            invalid ? `${provider.id}-spacing-error` : undefined
          }
          value={shown}
          disabled={provider.capability.supported === false}
          onChange={(event) => {
            setValue(event.target.value);
            setInvalid(false);
          }}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === "Enter") event.currentTarget.blur();
            if (event.key === "Escape") {
              setValue(null);
              setInvalid(false);
            }
          }}
        />
        {invalid && (
          <span
            className="set-cell-error"
            id={`${provider.id}-spacing-error`}
            role="alert"
          >
            A number from 0 to 3600
          </span>
        )}
      </td>
      <td data-numeric="">
        {formatNumber(Number(provider.runtime.requests_day ?? 0))}
      </td>
    </tr>
  );
}
