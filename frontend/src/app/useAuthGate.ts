import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { TOKEN_INVALID_EVENT, api, getToken } from "../api/client";
import { keys } from "../features/shared/queries";

/** Opens the token dialog when the server wants a token and none works. */
export function useAuthGate(): { open: boolean; close: () => void } {
  const auth = useQuery({ queryKey: keys.auth, queryFn: api.dashboardAuth });
  const [invalid, setInvalid] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const onInvalid = () => setInvalid(true);
    window.addEventListener(TOKEN_INVALID_EVENT, onInvalid);
    return () => window.removeEventListener(TOKEN_INVALID_EVENT, onInvalid);
  }, []);

  const missing = Boolean(auth.data?.token_required) && !getToken() && !dismissed;
  return {
    open: invalid || missing,
    close: () => {
      setInvalid(false);
      setDismissed(true);
    },
  };
}
