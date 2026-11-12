import type { Run } from "../../api";
import { Tag } from "../../design";
import { runStatus } from "./wording";

/** Finished, In progress or Interrupted. */
export function RunStatusTag({ run }: { run: Run }) {
  const status = runStatus[run.status];
  return <Tag tone={status.tone}>{status.label}</Tag>;
}

/** The run a question, a request or a change belongs to, as a link. */
export function RunLink({
  id,
  label = "its run",
}: {
  id: string;
  label?: string;
}) {
  return <a href={`#activity?section=runs&run=${id}`}>{label}</a>;
}
