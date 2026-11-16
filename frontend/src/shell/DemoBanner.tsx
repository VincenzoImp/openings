import { useState } from "react";
import { X } from "lucide-react";
import { IconButton } from "../ui/Button";

const KEY = "openings-demo-banner";

/** Whether the banner was dismissed in this browser session. */
function dismissed() {
  try {
    return sessionStorage.getItem(KEY) === "dismissed";
  } catch {
    return false;
  }
}

/**
 * The line above every screen of a demo workspace: the data is fictional,
 * nothing is kept and no job site is contacted. It can be put away for the
 * browser session (a recording does).
 */
export function DemoBanner() {
  const [hidden, setHidden] = useState(dismissed);
  if (hidden) return null;
  return (
    <section className="shell-demo" aria-label="Demo workspace">
      <p>
        <strong>Demo workspace</strong>
        <span>
          {" "}
          · fictional data · nothing is kept · no job site is contacted
        </span>
      </p>
      <IconButton
        icon={X}
        label="Hide for this session"
        size="sm"
        tooltip="none"
        onClick={() => {
          try {
            sessionStorage.setItem(KEY, "dismissed");
          } catch {
            // Hidden until the page reloads.
          }
          setHidden(true);
        }}
      />
    </section>
  );
}
