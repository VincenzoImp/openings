import { Tag } from "../../design";

/**
 * Marks a part of Settings that needs owner authority: the dashboard session
 * or an owner token may use it, an agent token is refused.
 */
export function OwnerOnly() {
  return (
    <Tag tone="info">
      Owner only<span className="sr">: an agent token is refused</span>
    </Tag>
  );
}
