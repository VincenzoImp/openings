import { useState } from "react";
import {
  knowledgeKinds,
  type Claim,
  type Knowledge,
  type ListResult,
} from "../api";
import { Button, ErrorBanner, Loading, Split, Tabs } from "../design";
import { PageHead, plural } from "../library/common";
import { useFresh } from "../library/useFresh";
import { confirmLeave, useDebounce, useUrlFilters } from "../state";
import { EntryEditor } from "./career/EntryEditor";
import { ImportDialog } from "./career/ImportDialog";
import { ProfileCard } from "./career/ProfileCard";
import { AllClaims, EntryList, RecordFilters } from "./career/Record";

const NO_ENTRIES: ListResult<Knowledge> = { items: [], total: 0 };
const NO_CLAIMS: ListResult<Claim> = { items: [], total: 0 };

export default function CareerPage() {
  // `section` keeps the links of earlier versions working: profile, knowledge, claims.
  const [filters, setFilters] = useUrlFilters({
    section: "profile",
    entry: "",
    q: "",
    kind: "",
    offset: "0",
    approved: "",
    knowledge_id: "",
  });
  const allClaims = filters.section === "claims";
  const query = useDebounce(filters.q);
  const entries = useFresh(
    `/career/knowledge?summary=true&limit=200&q=${allClaims ? "" : encodeURIComponent(query)}&kind=${allClaims ? "" : filters.kind}`,
    NO_ENTRIES,
    ["career", "files"],
  );
  const claims = useFresh("/career/claims?summary=true&limit=1", NO_CLAIMS, [
    "career",
  ]);
  const approved = useFresh(
    "/career/claims?summary=true&limit=1&approved=true",
    NO_CLAIMS,
    ["career"],
  );
  const [importing, setImporting] = useState(false);
  const [pane, setPane] = useState<0 | 1>(filters.entry ? 1 : 0);
  // Without a choice the first entry is open, as a list beside a detail expects.
  const kinds = Object.keys(knowledgeKinds);
  const first = [...entries.data.items].sort(
    (a, b) => kinds.indexOf(a.kind) - kinds.indexOf(b.kind),
  )[0];
  const selected = filters.entry || first?.id || "";
  const select = (entry: string) => {
    if (entry !== selected && !confirmLeave()) return;
    setFilters({ entry });
    setPane(1);
  };
  const add = (
    <Button size="sm" onClick={() => select("new")}>
      Add an entry
    </Button>
  );
  return (
    <>
      <PageHead title="Profile">
        Who you are and what you have done. Documents may only state what is
        recorded and approved here.
      </PageHead>
      <ProfileCard />
      <div className="spread record-head">
        <h2>Career record</h2>
        <div className="row">
          <span className="muted num">
            {plural(entries.data.total, "entry", "entries")} ·{" "}
            {plural(claims.data.total, "claim")} · {approved.data.total}{" "}
            approved
          </span>
          <Button size="sm" icon="upload" onClick={() => setImporting(true)}>
            Import
          </Button>
          {add}
        </div>
      </div>
      <Tabs
        id="career"
        label="Career record"
        value={allClaims ? "claims" : "record"}
        onChange={(tab) =>
          setFilters({
            section: tab === "claims" ? "claims" : "knowledge",
            q: "",
            offset: "0",
          })
        }
        items={[
          { id: "record", label: "Entries" },
          { id: "claims", label: "All claims" },
        ]}
      >
        {allClaims ? (
          <AllClaims
            filters={filters}
            onChange={setFilters}
            entries={entries.data.items}
          />
        ) : (
          <Split
            columns="minmax(0, 1fr) minmax(0, 1.25fr)"
            labels={["Record", "Selected entry"]}
            pane={pane}
            onPane={setPane}
          >
            <section className="card" aria-label="Entries by kind">
              <RecordFilters filters={filters} onChange={setFilters}>
                <select
                  className="input"
                  aria-label="Kind of entry"
                  value={filters.kind}
                  onChange={(event) => setFilters({ kind: event.target.value })}
                >
                  <option value="">All kinds</option>
                  {Object.entries(knowledgeKinds).map(([kind, label]) => (
                    <option key={kind} value={kind}>
                      {label}
                    </option>
                  ))}
                </select>
              </RecordFilters>
              {entries.error ? (
                <div className="body">
                  <ErrorBanner message={entries.error} retry={entries.reload} />
                </div>
              ) : entries.loading || filters.q !== query ? (
                <Loading label="Loading the record…" />
              ) : (
                <EntryList
                  entries={entries.data.items}
                  selected={selected}
                  onSelect={select}
                  filtered={!!(query || filters.kind)}
                  onAdd={add}
                />
              )}
              {entries.data.total > entries.data.items.length && (
                <footer>
                  <span className="muted">
                    The first {entries.data.items.length} of{" "}
                    {entries.data.total} entries are shown. Search to find the
                    others.
                  </span>
                </footer>
              )}
            </section>
            <EntryEditor
              id={entries.loading && !filters.entry ? "" : selected}
              onSaved={(entry) => setFilters({ entry: entry.id })}
              onRemoved={() => {
                setFilters({ entry: "" });
                setPane(0);
              }}
            />
          </Split>
        )}
      </Tabs>
      {importing && <ImportDialog onClose={() => setImporting(false)} />}
    </>
  );
}
