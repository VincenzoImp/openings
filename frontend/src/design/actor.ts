// Who made a change, as the API reports it: one label per write.
//   "owner"              the dashboard session or an owner token
//   "agent:<token name>" a scoped agent token
//   "system"             collection, the worker or an upgrade
//   null                 written before attribution was recorded

/** "by you", "by <token name>", "by job sources"; nothing when unknown. */
export function actorPhrase(label?: string | null) {
  if (!label) return "";
  if (label === "owner") return "by you";
  if (label === "system") return "by job sources";
  if (label.startsWith("agent:")) return `by ${label.slice(6) || "an agent"}`;
  return `by ${label}`;
}
