import { RefreshCw } from "lucide-react";
import { Button } from "../ui/Button";
import { Callout } from "../ui/Page";

/**
 * What a versioned form shows when its save met a newer version: the draft
 * stays; Reload takes the stored record, Keep editing keeps the draft.
 */
export function ConflictNotice({
  onReload,
  onKeepEditing,
}: {
  onReload: () => void;
  onKeepEditing: () => void;
}) {
  return (
    <div role="alert">
      <Callout
        icon={RefreshCw}
        tone="warning"
        title="Changed elsewhere"
        actions={
          <>
            <Button size="sm" onClick={onReload}>
              Reload
            </Button>
            <Button size="sm" variant="ghost" onClick={onKeepEditing}>
              Keep editing
            </Button>
          </>
        }
      >
        This record was saved in another place since you opened it. Your changes
        are still here.
      </Callout>
    </div>
  );
}
