// Who made a change, as the API reports it since 0.17 (`actor` objects).
export interface ActorLike {
  kind: "owner" | "token" | "system" | "unknown";
  name: string | null;
  token_kind?: "owner" | "agent" | null;
  label: string;
}
export interface ActorChipView {
  /** Class beside `actor`: the agent colour is used only for an agent. */
  tone: "owner" | "agent" | "system" | "unknown";
  text: string;
}

/** The chip for an actor: an agent shows its token name, never a generic word. */
export function actorChip(actor?: ActorLike | null): ActorChipView {
  if (!actor || actor.kind === "unknown")
    return { tone: "unknown", text: actor?.label || "Unknown" };
  if (actor.kind === "system")
    return { tone: "system", text: actor.label || "System" };
  if (actor.kind === "owner")
    return { tone: "owner", text: actor.label || "Owner" };
  const name = actor.name || actor.label || "API token";
  return actor.token_kind === "owner"
    ? { tone: "owner", text: `${name} (owner token)` }
    : { tone: "agent", text: name };
}
