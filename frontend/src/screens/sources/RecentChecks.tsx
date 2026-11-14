import { Button } from "../../ui/Button";
import { Disclosure } from "../../ui/Disclosure";
import { formatDate, formatFull } from "../../ui/format";
import { SkeletonRows } from "../../ui/Page";
import { useToast } from "../../ui/Toast";
import { checkLine, failedTasks, isActive, type CheckView } from "./model";
import { useRecentChecks, useRetryCheck, useStopCheck } from "./queries";

/**
 * The last twenty checks, collapsed at the bottom of the screen: when, which
 * source, what it found or why it failed, with Stop for one in progress and
 * Retry for one that failed.
 */
export function RecentChecks() {
  // The disclosure draws (and so reads) the checks only once opened.
  return (
    <Disclosure title="Recent checks" className="src-checks">
      <Checks />
    </Disclosure>
  );
}

function Checks() {
  const checks = useRecentChecks(true);
  const stop = useStopCheck();
  const retry = useRetryCheck();
  const toast = useToast();
  if (checks.isPending) return <SkeletonRows rows={3} />;
  if (checks.isError)
    return (
      <p className="src-checks-empty src-danger" role="alert">
        Recent checks could not be read. {checks.error.message}
      </p>
    );
  if (!checks.data.length)
    return (
      <p className="src-checks-empty">
        No check yet. Sources are checked on their schedule, or with Check now.
      </p>
    );
  const name = (check: CheckView) => check.source_name || "A removed source";
  return (
    <ul className="src-checks-list" aria-label="Recent checks">
      {checks.data.map((check) => {
        const when = check.started_at || check.created_at;
        const failed = check.state === "failed";
        const tasks = failedTasks(check);
        return (
          <li key={check.id} className="src-check">
            <span className="src-check-text">
              <span className="src-check-name">{name(check)}</span>
              <span className="src-check-line">
                <time dateTime={when} title={formatFull(when)}>
                  {formatDate(when)}
                </time>
                {" · "}
                <span className={failed ? "src-danger" : undefined}>
                  {checkLine(check)}
                </span>
              </span>
            </span>
            {isActive(check.state) ? (
              <Button
                size="sm"
                variant="ghost"
                aria-label={`Stop the check of ${name(check)}`}
                disabled={stop.isPending}
                onClick={() =>
                  stop.mutate(check.id, {
                    onSuccess: () =>
                      toast.show({
                        message: `Stopped the check of “${name(check)}”. Jobs it found stay.`,
                      }),
                    onError: (error) =>
                      toast.show({ message: error.message, tone: "error" }),
                  })
                }
              >
                Stop
              </Button>
            ) : failed && tasks.length && check.source_id ? (
              <Button
                size="sm"
                variant="ghost"
                aria-label={`Retry the check of ${name(check)}`}
                disabled={retry.isPending}
                onClick={() =>
                  retry.mutate(tasks, {
                    onSuccess: () =>
                      toast.show({
                        message: `Checking “${name(check)}” again`,
                      }),
                    onError: (error) =>
                      toast.show({ message: error.message, tone: "error" }),
                  })
                }
              >
                Retry
              </Button>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
