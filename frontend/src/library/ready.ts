import type { Json } from "../api";

/** Why the stored Ready step was cleared, from an application_ready_cleared event. */
const clearedReasons: Record<string, string> = {
  unmarked: "The mark was removed",
  document_created: "A new document revision was saved",
  document_deleted: "A document revision was deleted",
  file_uploaded: "A file was added to a current revision",
  blocking_requirement: "A blocking requirement is unresolved",
  left_preparing: "The application was sent or closed",
};
export function readyReason(payload?: Json) {
  const reason = payload?.reason;
  return typeof reason === "string"
    ? clearedReasons[reason] || reason.replaceAll("_", " ")
    : "";
}
