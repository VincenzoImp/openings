import { useRef } from "react";
import { Tabs } from "../design";
import { PageHead } from "../library/common";
import { useUrlState } from "../state";
import { Questions } from "./activity/Questions";
import { Requests } from "./activity/Requests";
import { Runs } from "./activity/Runs";
import { Timeline } from "./activity/Timeline";
import type { Links } from "./activity/records";

const TABS = ["questions", "requests", "runs", "timeline"];
// `section=changes` is the name the timeline had before it was rebuilt.
const sectionOf = (value: string) =>
  value === "changes" ? "timeline" : TABS.includes(value) ? value : "questions";

/**
 * What the agent asked, what the owner asked of it, what each run did, and
 * every change with who made it. `#activity?section=…` opens a tab and
 * `&run=…` a run; the filters of each tab are in the address too.
 */
export default function ActivityPage({
  openQuestions,
  ...links
}: Links & { openQuestions: number }) {
  const [raw] = useUrlState("section", "questions"),
    [run, setRun] = useUrlState("run", "");
  const section = sectionOf(raw);
  const opened = useRef(false);
  // A tab starts without the filters of the one before it.
  const show = (next: string) => {
    history.replaceState(
      null,
      "",
      next === "questions" ? "#activity" : `#activity?section=${next}`,
    );
    window.dispatchEvent(new PopStateEvent("popstate"));
  };
  return (
    <>
      <PageHead title="Activity">
        What your agent asked, what you asked of it, what it did in each run,
        and every change to the workspace with the name of who made it.
      </PageHead>
      <Tabs
        id="activity"
        label="Activity views"
        value={section}
        onChange={show}
        items={[
          {
            id: "questions",
            label: "Questions",
            count: openQuestions || undefined,
          },
          { id: "requests", label: "Requests" },
          { id: "runs", label: "Runs" },
          { id: "timeline", label: "Timeline" },
        ]}
      >
        {section === "runs" ? (
          <Runs
            run={run}
            autoFocus={opened.current}
            onRun={(id) => {
              opened.current = true;
              setRun(id);
              if (matchMedia("(max-width: 860px)").matches)
                window.scrollTo(0, 0);
            }}
            {...links}
          />
        ) : section === "timeline" ? (
          <Timeline {...links} />
        ) : section === "requests" ? (
          <Requests {...links} />
        ) : (
          <Questions {...links} />
        )}
      </Tabs>
    </>
  );
}
