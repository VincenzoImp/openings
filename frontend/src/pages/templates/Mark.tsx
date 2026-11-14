import { CircleCheck } from "lucide-react";
import { Icon } from "../../ui/Icon";

/** The one style of "Default", in the list and in the detail. */
export function DefaultMark({ kind }: { kind?: string }) {
  return (
    <span className="tpl-default">
      <Icon icon={CircleCheck} size="sm" />
      {kind ? `Default ${kind}` : "Default"}
    </span>
  );
}
