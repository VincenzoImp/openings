import { useState } from "react";
import { Button, Tabs } from "../design";
import { PageHead } from "../library/common";
import { confirmLeave, useUrlState } from "../state";
import { Master } from "./collection/Master";
import { Providers } from "./collection/Providers";
import { Runs } from "./collection/Runs";
import { Sources, type Editing } from "./collection/Sources";

// One file per tab: a tab added later (the yield of each source) is one more
// entry here and one more file in ./collection.
const TABS = [
  { id: "sources", label: "Sources" },
  { id: "runs", label: "Runs and tasks" },
  { id: "providers", label: "Providers" },
];
const tabOf = (value: string) =>
  TABS.some((tab) => tab.id === value) ? value : "sources";

/**
 * Where new jobs come from: saved searches and company boards with their
 * schedules, the runs and tasks that collected, and the request gate of each
 * provider. `#collection?section=…` opens a tab; its filters are in the
 * address too.
 */
export default function CollectionPage() {
  const [raw] = useUrlState("section", "sources");
  const section = tabOf(raw);
  const [editing, setEditing] = useState<Editing>(null);
  // A tab starts without the filters of the one before it.
  const show = (next: string) => {
    history.replaceState(
      null,
      "",
      next === "sources" ? "#collection" : `#collection?section=${next}`,
    );
    window.dispatchEvent(new PopStateEvent("popstate"));
  };
  const add = (kind: "search" | "board") => {
    if (editing && !confirmLeave()) return;
    if (section !== "sources") show("sources");
    setEditing(kind);
  };
  return (
    <>
      <PageHead
        title="Collection"
        actions={
          <>
            <Button onClick={() => add("board")}>Add a company board</Button>
            <Button variant="primary" onClick={() => add("search")}>
              Add a search
            </Button>
          </>
        }
      >
        Where new jobs come from: your saved searches and the company boards you
        follow, on the schedule you set.
      </PageHead>
      <Master />
      <Tabs
        id="collection"
        label="Collection views"
        value={section}
        onChange={show}
        items={TABS}
      >
        {section === "runs" ? (
          <Runs />
        ) : section === "providers" ? (
          <Providers />
        ) : (
          <Sources
            editing={editing}
            onEdit={(next) => {
              if (editing && next && !confirmLeave()) return;
              setEditing(next);
            }}
          />
        )}
      </Tabs>
    </>
  );
}
