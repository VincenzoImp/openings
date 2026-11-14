import { useState, type FormEvent } from "react";
import {
  api,
  copyText,
  tokenKinds,
  type ListResult,
  type TokenKind,
} from "../../api";
import {
  Banner,
  Button,
  EmptyState,
  ErrorBanner,
  Field,
  Loading,
  SegmentedControl,
  Tag,
} from "../../design";
import { ConfirmDialog } from "../../library/common";
import { dayTime } from "../../library/time";
import { useFresh } from "../../library/useFresh";
import { useWorkspace } from "../../state";
import { tokenAccess, type Token } from "./model";
import { OwnerOnly } from "./OwnerOnly";

const NONE: ListResult<Token> = { items: [], total: 0 };

/** The installation's API tokens with their kinds: create, read and revoke. */
export function Tokens() {
  const tokens = useFresh("/tokens", NONE, ["tokens"]);
  const [revoking, setRevoking] = useState<Token | null>(null);
  const { mutate } = useWorkspace();
  return (
    <>
      <section className="card" aria-labelledby="tokens-title">
        <header>
          <h2 id="tokens-title" className="grow">
            Tokens
          </h2>
          <OwnerOnly />
          <span className="caption">
            A token is shown once, when it is created
          </span>
        </header>
        {tokens.error ? (
          <div className="body">
            <ErrorBanner message={tokens.error} retry={tokens.reload} />
          </div>
        ) : tokens.loading ? (
          <Loading label="Loading tokens…" />
        ) : tokens.data.items.length ? (
          <div className="datatable-wrap">
            <table className="datatable stack" aria-label="API tokens">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Kind</th>
                  <th>Created</th>
                  <th>Last used</th>
                  <th>
                    <span className="sr">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {tokens.data.items.map((token) => {
                  return (
                    <tr key={token.id}>
                      <td className="primary">
                        <span className="title">{token.name}</span>
                        <div className="meta">{tokenAccess[token.kind]}</div>
                      </td>
                      <td>
                        <Tag
                          tone={token.kind === "agent" ? "agent" : "neutral"}
                        >
                          {tokenKinds[token.kind]}
                        </Tag>
                      </td>
                      <td className="meta" data-label="Created">
                        {dayTime(token.created_at)}
                      </td>
                      <td className="meta" data-label="Last used">
                        {token.last_used_at
                          ? dayTime(token.last_used_at)
                          : "Never"}
                      </td>
                      <td className="actions">
                        <Button
                          size="sm"
                          variant="quiet danger"
                          aria-label={`Revoke ${token.name}`}
                          onClick={() => setRevoking(token)}
                        >
                          Revoke
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No token yet">
            Create an agent token below to connect your agent.
          </EmptyState>
        )}
      </section>
      {revoking && (
        <ConfirmDialog
          title={`Revoke ${revoking.name}?`}
          confirm="Revoke token"
          keep="Keep token"
          onClose={() => setRevoking(null)}
          onConfirm={async () => {
            if (
              await mutate(
                () => api(`/tokens/${revoking.id}`, "DELETE"),
                `${revoking.name} was revoked.`,
              )
            )
              setRevoking(null);
          }}
        >
          <p>
            Anything that uses this token stops working at once. Its changes
            stay recorded with its name.
          </p>
        </ConfirmDialog>
      )}
    </>
  );
}

/** A new token of a chosen kind; the secret is shown once. */
export function CreateToken() {
  const { mutate, pending, notify } = useWorkspace();
  // An agent needs no owner authority, so that is the kind offered first.
  const [kind, setKind] = useState<TokenKind>("agent");
  const [created, setCreated] = useState<{
    name: string;
    token: string;
  } | null>(null);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const name = String(new FormData(form).get("name") || "").trim();
    let secret = "";
    if (
      await mutate(async () => {
        secret = (
          await api<{ token: string }>("/tokens", "POST", { name, kind })
        ).token;
      }, `${name} was created. Copy the token now.`)
    ) {
      setCreated({ name, token: secret });
      form.reset();
    }
  }
  return (
    <section className="card" aria-labelledby="create-title">
      <header>
        <h2 id="create-title" className="grow">
          Create a token
        </h2>
        <OwnerOnly />
      </header>
      <div className="body stack">
        <form className="new-token" onSubmit={create}>
          <Field label="Token name">
            <input
              name="name"
              required
              maxLength={100}
              placeholder="career-agent"
              autoComplete="off"
            />
          </Field>
          <div className="field">
            <span className="field-label" aria-hidden="true">
              Token kind
            </span>
            <SegmentedControl
              label="Token kind"
              value={kind}
              onChange={(next) => setKind(next as TokenKind)}
              options={[
                { id: "agent", label: "Agent" },
                { id: "owner", label: "Owner" },
              ]}
            />
          </div>
          <Button variant="primary" disabled={pending}>
            Create
          </Button>
        </form>
        <p className="caption token-kind">{tokenAccess[kind]}</p>
        <p className="caption">
          The name is shown next to every change the token makes. Use one token
          per agent, so its changes carry its name.
        </p>
        {created && (
          <Banner
            tone="info"
            role="status"
            title={`${created.name} was created. Copy the token now; it is not shown again.`}
            action={
              <Button size="sm" onClick={() => setCreated(null)}>
                I have saved it
              </Button>
            }
          >
            <pre className="code wrap secret">{created.token}</pre>
            <Button
              size="sm"
              icon="copy"
              onClick={() =>
                copyText(created.token)
                  .then(() => notify("Token copied."))
                  .catch(() => notify("Select and copy the token."))
              }
            >
              Copy the token
            </Button>
          </Banner>
        )}
      </div>
    </section>
  );
}
