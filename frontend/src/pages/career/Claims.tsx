import { useState } from "react";
import {
  api,
  claimRoles,
  version,
  type Claim,
  type Knowledge,
  type ListResult,
} from "../../api";
import { Button, ErrorBanner, Loading, Switch, Tag } from "../../design";
import { ConfirmDialog } from "../../library/common";
import { useFresh } from "../../library/useFresh";
import { useWorkspace } from "../../state";
import { ClaimDialog } from "./ClaimDialog";

const NONE: ListResult<Claim> = { items: [], total: 0 };

/**
 * One claim: its wording, whether documents may use it, and the typed
 * selection fields as controls that save at once.
 */
export function ClaimRow({
  claim,
  showEntry = false,
  onEdit,
  onSaved,
}: {
  claim: Claim;
  /** The claim as the server returned it after a control saved it. */
  onSaved: (claim: Claim) => void;
  /** Name the entry the claim belongs to (the list of all claims). */
  showEntry?: boolean;
  onEdit: (claim: Claim) => void;
}) {
  const { mutate, pending, notify } = useWorkspace();
  const [removing, setRemoving] = useState(false);
  const text = claim.text_preview ?? claim.text;
  const short = text.length > 60 ? text.slice(0, 60) + "…" : text;
  const patch = (fields: Partial<Claim>, message: string) =>
    mutate(async () => {
      const saved = await api<Claim>(
        `/career/claims/${claim.id}`,
        "PATCH",
        version(claim, fields),
      );
      // The next control uses the new version at once, before the list is read again.
      onSaved({ ...claim, ...saved });
    }, message);
  const entry = [claim.knowledge_title, claim.knowledge_organization]
    .filter(Boolean)
    .join(" · ");
  return (
    <div className="claim">
      <div className="spread claim-text">
        <p className="prose grow">{text}</p>
        {claim.approved ? (
          <Tag tone="ready">Approved</Tag>
        ) : (
          <Tag tone="attention">Not approved by you</Tag>
        )}
      </div>
      {showEntry && entry && <div className="caption">{entry}</div>}
      <div className="claim-controls">
        <Switch
          label={`Default in CV: ${short}`}
          checked={claim.default_in_cv}
          disabled={pending || !claim.approved}
          onChange={(checked) =>
            patch(
              { default_in_cv: checked },
              checked
                ? "The claim is in the CV by default."
                : "The claim is left out by default.",
            )
          }
        >
          Default in CV
        </Switch>
        <label>
          Role
          <select
            className="input"
            aria-label={`Role of: ${short}`}
            value={claim.role}
            disabled={pending}
            onChange={(event) =>
              patch(
                { role: event.target.value as Claim["role"] },
                "Role saved.",
              )
            }
          >
            {Object.entries(claimRoles).map(([role, label]) => (
              <option key={role} value={role}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Group
          <input
            className="input"
            key={claim.version}
            aria-label={`Group of: ${short}`}
            list="claim-groups"
            maxLength={100}
            placeholder="No group"
            defaultValue={claim.group}
            disabled={pending}
            onKeyDown={(event) => {
              if (event.key === "Enter") event.currentTarget.blur();
            }}
            onBlur={(event) => {
              const group = event.target.value.trim();
              if (group !== claim.group) void patch({ group }, "Group saved.");
            }}
          />
        </label>
      </div>
      <div className="row rule-state">
        <Button
          size="sm"
          disabled={pending}
          aria-label={`${claim.approved ? "Mark as draft" : "Approve"}: ${short}`}
          onClick={() =>
            patch(
              { approved: !claim.approved },
              claim.approved ? "Claim marked as draft." : "Claim approved.",
            )
          }
        >
          {claim.approved ? "Mark as draft" : "Approve"}
        </Button>
        <Button
          size="sm"
          aria-label={`Edit claim: ${short}`}
          onClick={() =>
            api<Claim>(`/career/claims/${claim.id}`)
              .then(onEdit)
              .catch((cause) => notify(cause.message, true))
          }
        >
          Edit
        </Button>
        <Button
          size="sm"
          variant="quiet danger"
          disabled={pending}
          aria-label={`Remove claim: ${short}`}
          onClick={() => setRemoving(true)}
        >
          Remove
        </Button>
        {!claim.approved && (
          <span className="caption">
            Documents cannot use it until you approve it.
          </span>
        )}
      </div>
      {removing && (
        <ConfirmDialog
          title="Remove this claim?"
          confirm="Remove claim"
          keep="Keep claim"
          onClose={() => setRemoving(false)}
          onConfirm={async () => {
            if (
              await mutate(
                () =>
                  api(
                    `/career/claims/${claim.id}?expected_version=${claim.version}`,
                    "DELETE",
                  ),
                "Claim removed.",
              )
            )
              setRemoving(false);
          }}
        >
          <p className="prose">{text}</p>
          <p className="muted">
            Applications that were already prepared keep their copy.
          </p>
        </ConfirmDialog>
      )}
    </div>
  );
}

/** A list of claims with one of them replaced by its saved state. */
export const replaced = (saved: Claim) => (list: ListResult<Claim>) => ({
  ...list,
  items: list.items.map((item) => (item.id === saved.id ? saved : item)),
});

/** The group names in use, offered while a group is typed. */
export function ClaimGroups({ claims }: { claims: Claim[] }) {
  const groups = [
    ...new Set(claims.map((claim) => claim.group).filter(Boolean)),
  ].sort();
  return (
    <datalist id="claim-groups">
      {groups.map((group) => (
        <option key={group} value={group} />
      ))}
    </datalist>
  );
}

/** The claims of one entry, inside its editor. */
export function EntryClaims({ entry }: { entry: Knowledge }) {
  const { data, setData, loading, error, reload } = useFresh(
    `/career/claims?knowledge_id=${entry.id}&limit=200&summary=false`,
    NONE,
    ["career"],
  );
  const [editing, setEditing] = useState<Claim | "new" | null>(null);
  return (
    <div className="sub flush">
      <div className="spread">
        <h3>
          Claims <span className="muted num">{data.total}</span>
        </h3>
        <Button size="sm" onClick={() => setEditing("new")}>
          Add a claim
        </Button>
      </div>
      {error ? (
        <div className="body">
          <ErrorBanner message={error} retry={reload} />
        </div>
      ) : loading ? (
        <Loading label="Loading claims…" />
      ) : data.items.length ? (
        data.items.map((claim) => (
          <ClaimRow
            key={claim.id}
            claim={claim}
            onEdit={setEditing}
            onSaved={(saved) => setData(replaced(saved))}
          />
        ))
      ) : (
        <p className="claim muted">
          No claims yet. Add a result, a responsibility or a skill in the words
          a CV could use.
        </p>
      )}
      <ClaimGroups claims={data.items} />
      {editing && (
        <ClaimDialog
          record={editing === "new" ? undefined : editing}
          entry={entry}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}
