import { CircleAlert } from "lucide-react";
import { Button } from "./Button";
import { Callout } from "./Page";

/**
 * The one way a screen says that its data could not be read: an inline
 * banner in plain words with Try again; what is already shown stays. The
 * technical cause goes to the console, not to the person.
 */
export function LoadError({
  what,
  error,
  retry,
}: {
  /** What could not be read, as a phrase: "your applications". */
  what: string;
  error?: unknown;
  retry?: () => void;
}) {
  if (error) console.error(error);
  return (
    <div role="alert" className="ui-load-error">
      <Callout
        icon={CircleAlert}
        tone="danger"
        title={`Couldn't load ${what}.`}
        actions={
          retry && (
            <Button size="sm" onClick={retry}>
              Try again
            </Button>
          )
        }
      >
        Check your connection and try again.
      </Callout>
    </div>
  );
}
