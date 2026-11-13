import { useEffect, useState } from "react";
import { Banner, Button } from "../../design";
import { SETUP_KEY, markSetup, setupMark } from "../../shell/setup";

/**
 * After the setup guide opened by itself on a new workspace, Today offers to
 * continue it until it is finished or put aside.
 */
export function SetupBanner() {
  const [mark, setMark] = useState(setupMark);
  useEffect(() => {
    const sync = () => setMark(setupMark());
    const storage = (event: StorageEvent) => {
      if (event.key === SETUP_KEY) sync();
    };
    window.addEventListener("openings:setup", sync);
    window.addEventListener("storage", storage);
    return () => {
      window.removeEventListener("openings:setup", sync);
      window.removeEventListener("storage", storage);
    };
  }, []);
  if (mark !== "started") return null;
  return (
    <Banner
      tone="info"
      title="Your workspace is not set up yet."
      action={
        <div className="row">
          <a className="btn sm primary" href="#setup">
            Continue setting up
          </a>
          <Button
            size="sm"
            variant="quiet"
            onClick={() => markSetup("skipped")}
          >
            Not now
          </Button>
        </div>
      }
    >
      The setup guide shows what is done: your agent, your profile, your policy
      and a first search.
    </Banner>
  );
}
