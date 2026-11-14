import { useEffect, useMemo, useRef, useState } from "react";
import type { JobList, Preferences } from "../api";
import { Button, Card, EmptyState, Split, Tabs } from "../design";
import { PageHead } from "../library/common";
import { useFresh } from "../library/useFresh";
import { useDebounce, useUrlFilters } from "../state";
import type { Links } from "../library/records";
import { AddJob } from "./jobs/AddJob";
import { Detail } from "./jobs/Detail";
import {
  DEFAULTS,
  JOB_SCOPES,
  neighbour,
  ownLanguages,
  QUEUE_SECTIONS,
  SECTIONS,
  sectionCount,
  sectionOf,
  type Filters,
} from "./jobs/model";
import { Queue } from "./jobs/Queue";

const NONE: JobList = { items: [], total: 0 };

/**
 * Everything collection found, in four tabs: the jobs to review, the
 * Shortlist, the dismissed jobs and all of them, each beside the selected
 * job. `#jobs?section=…&job=…` opens a tab and a job; the shell rewrites the
 * old Inbox, Shortlist and `?job=` addresses (shell/routes.ts).
 */
export default function JobsPage({ onOpenApplication }: Links) {
  const [values, setValues] = useUrlFilters(DEFAULTS);
  const filters = values as Filters;
  const section = sectionOf(filters.section);
  const [adding, setAdding] = useState(false);
  // On a phone one pane is shown: the selected job, or the list.
  const [pane, setPane] = useState<0 | 1>(filters.job ? 1 : 0);
  useEffect(() => {
    if (filters.job) setPane(1);
  }, [filters.job]);
  const q = useDebounce(filters.q);
  const counted = new URLSearchParams({ limit: "1", include_counts: "true" });
  if (q) counted.set("q", q);
  // The tabs count what their lists show, hidden languages included.
  if (filters.hide_unspoken === "true")
    counted.set("hide_unspoken_required", "true");
  const counts = useFresh<JobList>(`/jobs?${counted}`, NONE, JOB_SCOPES);
  const preferences = useFresh<Preferences | null>("/preferences", null, [
    "preferences",
    "settings",
  ]);
  const own = useMemo(
    () => ownLanguages(preferences.data?.settings.spoken_languages),
    [preferences.data],
  );
  const select = (job: string) => {
    setValues({ job });
    setPane(1);
  };
  // The rows of the list, to move on from a job that leaves it.
  const rows = useRef<string[]>([]);
  /**
   * Before a triage of `id`: in To review and the Shortlist, where the job
   * leaves the list, returns what shows the next row (or the previous one at
   * the end) once the change is saved.
   */
  const leaving = (id: string) => {
    if (!QUEUE_SECTIONS.includes(section) || id !== filters.job) return null;
    const next = neighbour(rows.current, id);
    return () => {
      setValues({ job: next });
      if (!next) setPane(0);
    };
  };
  return (
    <>
      <PageHead
        title="Jobs"
        actions={
          <Button icon="plus" onClick={() => setAdding(true)}>
            Add a job
          </Button>
        }
      >
        Everything collection found. Your agent reviews new jobs against your
        preferences; you can shortlist or dismiss any of them yourself, and
        every dismissal can be restored.
      </PageHead>
      <Tabs
        id="jobs"
        label="Jobs by triage state"
        value={section}
        onChange={(id) =>
          setValues({
            section: id,
            offset: "0",
            dismissed_by: "",
            sort: "",
          })
        }
        items={SECTIONS.map((item) => ({
          ...item,
          count: sectionCount(item.id, counts.data.counts),
        }))}
      >
        <div className="stack jobs-panel">
          <Split
            columns="minmax(0, 1.15fr) minmax(0, 1fr)"
            labels={filters.job ? ["List", "Selected job"] : undefined}
            pane={pane}
            onPane={setPane}
          >
            <Queue
              section={section}
              filters={filters}
              setFilters={(patch) => setValues(patch as Record<string, string>)}
              counts={counts.data.counts}
              own={own}
              selected={filters.job}
              onSelect={select}
              onRows={(ids) => {
                rows.current = ids;
              }}
              leaving={leaving}
              onAdd={() => setAdding(true)}
            />
            {filters.job ? (
              <Detail
                key={filters.job}
                id={filters.job}
                own={own}
                onOpenApplication={onOpenApplication}
                onOpenJob={select}
                leaving={leaving}
                onGone={() => {
                  setValues({ job: "" });
                  setPane(0);
                }}
              />
            ) : (
              <Card className="detail only-desktop">
                <EmptyState title="No job selected">
                  Choose a job to read its posting, its signals and its history.
                </EmptyState>
              </Card>
            )}
          </Split>
        </div>
      </Tabs>
      {adding && (
        <AddJob
          onClose={() => setAdding(false)}
          onOpenJob={(job) => {
            setAdding(false);
            setValues({ section: "review", job, offset: "0" });
            setPane(1);
          }}
        />
      )}
    </>
  );
}
