import { useState, type FormEvent, type ReactNode } from "react";
import { Ellipsis, ExternalLink, KeyRound, Plus, Trash2 } from "lucide-react";
import { Button, IconButton } from "../../ui/Button";
import { CodeBlock } from "../../ui/CodeBlock";
import { ConfirmDialog, Dialog } from "../../ui/Dialog";
import { Field, Input, Select } from "../../ui/Field";
import { formatDay, formatFull } from "../../ui/format";
import { Icon } from "../../ui/Icon";
import { Menu } from "../../ui/Menu";
import { SkeletonRows } from "../../ui/Page";
import { useToast } from "../../ui/Toast";
import { ago } from "../sources/model";
import {
  ACCESS,
  CLIENTS,
  accessOf,
  connectSnippet,
  type ClientId,
  type TokenKind,
} from "./model";
import {
  useCreateToken,
  useIsOwner,
  useRevokeToken,
  useSkills,
  useTokens,
  useWorkspaceInfo,
  type TokenRow,
} from "./queries";
import { OwnerOnly, SettingsSection } from "./Rows";

/**
 * Connecting an agent in three numbered steps: a token, the agent's MCP
 * configuration, and what to ask it. Openings itself runs no AI.
 */
export function Agents() {
  const owner = useIsOwner();
  const info = useWorkspaceInfo();
  const origin = info.data?.origin || location.origin;
  return (
    <SettingsSection
      title="API & agents"
      lead="Openings has no AI of its own; nothing happens until you ask your agent."
    >
      <ol className="set-steps">
        <Step number={1} title="Create a token" note={owner && <OwnerOnly />}>
          {owner ? (
            <Tokens />
          ) : (
            <p className="set-row-desc">
              Ask the owner of this workspace for a token.
            </p>
          )}
        </Step>
        <Step number={2} title="Add Openings to your agent">
          <ConnectSnippet origin={origin} />
        </Step>
        <Step number={3} title="Open your agent and ask">
          <AskList />
        </Step>
      </ol>
    </SettingsSection>
  );
}

function Step({
  number,
  title,
  note,
  children,
}: {
  number: number;
  title: string;
  note?: ReactNode;
  children: ReactNode;
}) {
  return (
    <li className="set-step">
      <span className="set-step-number" aria-hidden="true">
        {number}
      </span>
      <div className="set-step-body">
        <h3 className="set-step-title">
          <span className="ui-sr">Step {number}: </span>
          {title}
          {note}
        </h3>
        {children}
      </div>
    </li>
  );
}

/** The API tokens, newest first, with New token and Revoke. */
export function Tokens() {
  const tokens = useTokens();
  const revoke = useRevokeToken();
  const toast = useToast();
  const [creating, setCreating] = useState(false);
  const [revoking, setRevoking] = useState<TokenRow | null>(null);
  return (
    <div className="set-tokens">
      {tokens.isPending ? (
        <SkeletonRows rows={2} />
      ) : tokens.isError ? (
        <p className="set-row-desc set-danger" role="alert">
          The tokens could not be read. {tokens.error.message}
        </p>
      ) : tokens.data.length ? (
        <ul className="set-list" aria-label="API tokens">
          {tokens.data.map((token) => (
            <li key={token.id} className="set-item">
              <Icon icon={KeyRound} className="set-item-icon" />
              <span className="set-item-text">
                <span className="set-item-title">{token.name}</span>
                <span className="set-item-sub">
                  {ACCESS[accessOf(token.kind)].label} · Created{" "}
                  <span title={formatFull(token.created_at)}>
                    {formatDay(token.created_at)}
                  </span>{" "}
                  ·{" "}
                  {token.last_used_at ? (
                    <span title={formatFull(token.last_used_at)}>
                      Last used {ago(token.last_used_at)}
                    </span>
                  ) : (
                    "Never used"
                  )}
                </span>
              </span>
              <Menu
                label={`Actions for ${token.name}`}
                placement="bottom-end"
                items={[
                  {
                    id: "revoke",
                    label: "Revoke…",
                    icon: Trash2,
                    danger: true,
                    onSelect: () => setRevoking(token),
                  },
                ]}
                trigger={(props) => (
                  <IconButton
                    {...props}
                    icon={Ellipsis}
                    label={`More actions for ${token.name}`}
                    size="sm"
                    tooltip="above"
                    className="set-item-more"
                  />
                )}
              />
            </li>
          ))}
        </ul>
      ) : (
        <p className="set-row-desc">No token yet.</p>
      )}
      <div>
        <Button icon={Plus} onClick={() => setCreating(true)}>
          New token
        </Button>
      </div>
      <NewTokenDialog open={creating} onClose={() => setCreating(false)} />
      <ConfirmDialog
        open={!!revoking}
        title={`Revoke “${revoking?.name ?? ""}”?`}
        confirm="Revoke token"
        onClose={() => setRevoking(null)}
        onConfirm={() => {
          const token = revoking;
          if (!token) return;
          revoke.mutate(token.id, {
            onSuccess: () =>
              toast.show({
                message: `Revoked “${token.name}”`,
                tone: "success",
              }),
            onError: (error) =>
              toast.show({ message: error.message, tone: "error" }),
          });
        }}
      >
        An agent using it is refused from now on. This cannot be undone; create
        a new token to connect it again.
      </ConfirmDialog>
    </div>
  );
}

/**
 * A new token: a name and its access (Agent preselected). The secret is
 * shown once, with a copy button, before the dialog closes.
 */
export function NewTokenDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const create = useCreateToken();
  const toast = useToast();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<TokenKind>("agent");
  const [submitted, setSubmitted] = useState(false);
  const [secret, setSecret] = useState("");
  const close = () => {
    setName("");
    setKind("agent");
    setSubmitted(false);
    setSecret("");
    onClose();
  };
  function save(event: FormEvent) {
    event.preventDefault();
    setSubmitted(true);
    if (!name.trim()) return;
    create.mutate(
      { name: name.trim(), kind },
      {
        onSuccess: (token) => setSecret(token.token ?? ""),
        onError: (error) =>
          toast.show({ message: error.message, tone: "error" }),
      },
    );
  }
  return (
    <Dialog
      open={open}
      onClose={close}
      dismissible={!secret}
      title={secret ? "Copy your token" : "New token"}
      description={
        secret
          ? "It is shown only this once. Keep it in your agent's OPENINGS_TOKEN environment variable."
          : undefined
      }
      initialFocus="input"
      footer={
        secret ? (
          <Button variant="primary" onClick={close}>
            Done
          </Button>
        ) : (
          <>
            <Button variant="ghost" onClick={close}>
              Cancel
            </Button>
            <Button
              variant="primary"
              type="submit"
              form="token-form"
              disabled={create.isPending}
            >
              Create token
            </Button>
          </>
        )
      }
    >
      {secret ? (
        <CodeBlock
          code={secret}
          label="Token"
          onCopied={(ok) =>
            toast.show(
              ok
                ? { message: "Token copied", tone: "success" }
                : { message: "Select the token and copy it.", tone: "error" },
            )
          }
        />
      ) : (
        <form id="token-form" className="set-form" noValidate onSubmit={save}>
          <Field
            label="Name"
            hint="Which agent uses it, such as Claude Code on my laptop."
            error={submitted && !name.trim() ? "Give the token a name." : ""}
          >
            <Input
              value={name}
              maxLength={120}
              autoComplete="off"
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <fieldset className="set-access">
            <legend className="ui-field-label">Access</legend>
            {(Object.keys(ACCESS) as TokenKind[]).map((value) => (
              <label key={value} className="set-choice">
                <input
                  type="radio"
                  name="token-access"
                  value={value}
                  checked={kind === value}
                  onChange={() => setKind(value)}
                />
                <span className="set-choice-text">
                  <span className="set-choice-title">
                    {ACCESS[value].label}
                  </span>
                  <span className="set-choice-desc">
                    {ACCESS[value].detail}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>
        </form>
      )}
    </Dialog>
  );
}

/** The MCP configuration of Claude Code or Codex, and the REST address. */
export function ConnectSnippet({ origin }: { origin: string }) {
  const [client, setClient] = useState<ClientId>("claude");
  const toast = useToast();
  const base = origin.replace(/\/$/, "");
  return (
    <div className="set-connect">
      <Select
        aria-label="Agent"
        className="set-select"
        value={client}
        onChange={(event) => setClient(event.target.value as ClientId)}
      >
        {CLIENTS.map((item) => (
          <option key={item.id} value={item.id}>
            {item.label}
          </option>
        ))}
      </Select>
      <CodeBlock
        code={connectSnippet(client, base)}
        label="MCP configuration"
        onCopied={(ok) =>
          toast.show(
            ok
              ? { message: "Configuration copied", tone: "success" }
              : {
                  message: "Select the configuration and copy it.",
                  tone: "error",
                },
          )
        }
      />
      <p className="set-row-desc">
        Put the token from step 1 in the OPENINGS_TOKEN environment variable,
        never in the file. Scripts use the REST API at{" "}
        <code className="set-code">{base}/api/v1</code> with the same token.{" "}
        <a
          href="/api/docs"
          target="_blank"
          rel="noreferrer"
          className="set-nowrap"
        >
          API reference
          <Icon icon={ExternalLink} size="sm" className="set-external" />
        </a>
      </p>
    </div>
  );
}

/** What the shipped skills let the owner ask: a title, a line, an example. */
function AskList() {
  const skills = useSkills();
  if (skills.isPending) return <SkeletonRows rows={3} />;
  if (skills.isError)
    return (
      <p className="set-row-desc set-danger" role="alert">
        The list could not be read. {skills.error.message}
      </p>
    );
  if (!skills.data.length)
    return (
      <p className="set-row-desc">
        This installation serves no skills; your agent can still use every tool.
      </p>
    );
  return (
    <>
      <h4 className="set-ask-title">What you can ask your agent</h4>
      <ul className="set-ask" aria-label="What you can ask your agent">
        {skills.data.map((skill) => (
          <li key={skill.name}>
            <span className="set-ask-name">{skill.title || skill.name}</span>
            {skill.summary && (
              <span className="set-ask-summary">{skill.summary}</span>
            )}
            {skill.example && (
              <span className="set-ask-example">“{skill.example}”</span>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}
