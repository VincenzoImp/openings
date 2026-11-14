import { useState } from "react";
import {
  api,
  version,
  type Claim,
  type Knowledge,
  type ListResult,
} from "../../api";
import { Button, ErrorBanner, IconButton, Loading, Tag } from "../../design";
import { ConfirmDialog } from "../../library/common";
import { useFresh } from "../../library/useFresh";
import { useWorkspace } from "../../state";
import { ClaimDialog } from "./ClaimDialog";

const NONE: ListResult<Claim> = { items: [], total: 0 };

/**
 * One claim: its wording, whether you approved it, the star that keeps it in
 * every CV, and a menu with Edit and Delete.
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
  const [menu, setMenu] = useState(false);
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
  const entry = [claim.career_title, claim.career_organization]
    .filter(Boolean)
    .join(" · ");
  return (
    <div className="claim">
      <div className="spread claim-text">
        <p className="prose grow">{text}</p>
        {claim.approved ? (
          <Tag tone="ready">Approved</Tag>
        ) : (
          <Tag tone="attention">Not approved</Tag>
        )}
      </div>
      {showEntry && entry && <div className="caption">{entry}</div>}
      <div className="row rule-state">
        {!claim.approved && (
          <Button
            size="sm"
            disabled={pending}
            aria-label={`Approve: ${short}`}
            onClick={() => patch({ approved: true }, "Claim approved.")}
          >
            Approve
          </Button>
        )}
        <Button
          size="sm"
          variant="quiet"
          className="star"
          disabled={pending}
          aria-pressed={claim.always_include}
          aria-label={`Always include in my CV: ${short}`}
          title="Always include in my CV"
          onClick={() =>
            patch(
              { always_include: !claim.always_include },
              claim.always_include
                ? "The claim is no longer always included."
                : "The claim is always included in your CV.",
            )
          }
        >
          <span aria-hidden="true">{claim.always_include ? "★" : "☆"}</span>
        </Button>
        {menu && (
          <>
            <Button
              size="sm"
              aria-label={`Edit claim: ${short}`}
              onClick={() => {
                setMenu(false);
                api<Claim>(`/career/claims/${claim.id}`)
                  .then(onEdit)
                  .catch((cause) => notify(cause.message, true));
              }}
            >
              Edit
            </Button>
            <Button
              size="sm"
              variant="quiet danger"
              disabled={pending}
              aria-label={`Delete claim: ${short}`}
              onClick={() => {
                setMenu(false);
                setRemoving(true);
              }}
            >
              Delete
            </Button>
          </>
        )}
        <IconButton
          icon="more"
          label={`More actions for claim: ${short}`}
          aria-expanded={menu}
          onClick={() => setMenu(!menu)}
        />
        {!claim.approved && (
          <span className="caption">
            Documents cannot use it until you approve it.
          </span>
        )}
      </div>
      {removing && (
        <ConfirmDialog
          title="Delete this claim?"
          confirm="Delete claim"
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
                "Claim deleted.",
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

/** The claims of one entry, inside its editor. */
export function EntryClaims({ entry }: { entry: Knowledge }) {
  const { data, setData, loading, error, reload } = useFresh(
    `/career/claims?career_id=${entry.id}&limit=200&summary=false`,
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
