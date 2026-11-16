import { useState } from "react";
import { Info } from "lucide-react";
import { useWorkspaceInfo } from "../screens/settings/queries";
import { Button } from "../ui/Button";
import { Callout } from "../ui/Page";
import { addressNotice } from "./address";
import "./address.css";

const KEY = "openings.address-notice";

function dismissed(fix: string) {
  try {
    return localStorage.getItem(KEY) === fix;
  } catch {
    return false;
  }
}

/**
 * Above every screen, when the dashboard is open at an address agents and
 * upload links do not use: the variable to set so they work from here too.
 */
export function AddressNotice() {
  const info = useWorkspaceInfo();
  const notice = addressNotice(info.data?.origin, location.origin);
  const [hidden, setHidden] = useState(false);
  if (!notice || hidden || dismissed(notice.fix)) return null;
  return (
    <div className="shell-address">
      <Callout
        icon={Info}
        tone="warning"
        title={`Agents and upload links use ${notice.used}.`}
        actions={
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              try {
                localStorage.setItem(KEY, notice.fix);
              } catch {}
              setHidden(true);
            }}
          >
            Dismiss
          </Button>
        }
      >
        To use this address, set <code>{notice.fix}</code> and restart Openings.
      </Callout>
    </div>
  );
}
