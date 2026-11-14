import { useState } from "react";
import {
  careerDates,
  careerEntryLabel,
  knowledgeKinds,
  type Claim,
  type Knowledge,
  type KnowledgeKind,
  type ListResult,
} from "../../api";
import { EmptyState, ErrorBanner, Loading, Tag } from "../../design";
import { Pager, plural } from "../../library/common";
import { useFresh } from "../../library/useFresh";
import { useDebounce } from "../../state";
import { ClaimDialog } from "./ClaimDialog";
import { ClaimRow, replaced } from "./Claims";

/** Search and kind filters above the record. */
export function RecordFilters({
  filters,
  onChange,
  children,
}: {
  filters: Record<string, string>;
  onChange: (patch: Record<string, string>) => void;
  /** More filters after the search box. */
  children?: React.ReactNode;
}) {
  return (
    <div className="filters" role="search">
      <input
        className="input"
        type="search"
        aria-label="Search the record"
        placeholder="Search titles, organizations and text"
        value={filters.q}
        onChange={(event) => onChange({ q: event.target.value, offset: "0" })}
      />
      {children}
    </div>
  );
}

/** The entries grouped by kind; the selected one is edited beside the list. */
export function EntryList({
  entries,
  selected,
  onSelect,
  filtered,
  onAdd,
}: {
  entries: Knowledge[];
  selected: string;
  onSelect: (id: string) => void;
  /** A search or kind filter is active. */
  filtered: boolean;
  onAdd: React.ReactNode;
}) {
  if (!entries.length)
    return filtered ? (
      <EmptyState title="No entry matches">
        Change the search or the kind to see more of your record.
      </EmptyState>
    ) : (
      <EmptyState title="Your record is empty" action={onAdd}>
        Add what you have done: jobs, projects, education, languages. A title is
        enough to start; facts and claims can follow.
      </EmptyState>
    );
  const kinds = (Object.keys(knowledgeKinds) as KnowledgeKind[]).filter(
    (kind) => entries.some((entry) => entry.kind === kind),
  );
  return (
    <>
      {kinds.map((kind) => (
        <div key={kind}>
          <h3 className="kind eyebrow">{knowledgeKinds[kind]}</h3>
          <ul className="list entries">
            {entries
              .filter((entry) => entry.kind === kind)
              .map((entry) => {
                const claims = entry.highlight_count ?? 0;
                return (
                  <li
                    key={entry.id}
                    className={
                      entry.id === selected ? "is-selected" : undefined
                    }
                  >
                    <div className="grow">
                      <button
                        type="button"
                        className="title"
                        aria-current={entry.id === selected || undefined}
                        aria-label={`Open ${careerEntryLabel(entry)}`}
                        onClick={() => onSelect(entry.id)}
                      >
                        {entry.title}
                      </button>
                      <div className="meta">
                        {[entry.organization, careerDates(entry.dates)]
                          .filter(Boolean)
                          .join(" · ")}
                      </div>
                      {!!entry.skills.length && (
                        <div className="row tags">
                          {entry.skills.slice(0, 3).map((skill) => (
                            <Tag key={skill}>{skill}</Tag>
                          ))}
                          {entry.skills.length > 3 && (
                            <span className="caption">
                              +{entry.skills.length - 3}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    {claims ? (
                      <span className="caption num nowrap">
                        {plural(claims, "claim")}
                        {entry.file_count
                          ? ` · ${plural(entry.file_count, "file")}`
                          : ""}
                      </span>
                    ) : (
                      <Tag tone="attention">No claims yet</Tag>
                    )}
                  </li>
                );
              })}
          </ul>
        </div>
      ))}
    </>
  );
}

/** Every claim of the record, to search and to approve across entries. */
export function AllClaims({
  filters,
  onChange,
  entries,
}: {
  filters: Record<string, string>;
  onChange: (patch: Record<string, string>) => void;
  entries: Knowledge[];
}) {
  const query = useDebounce(filters.q);
  const { data, setData, loading, error, reload } = useFresh<ListResult<Claim>>(
    `/career/claims?summary=true&limit=30&offset=${filters.offset}&q=${encodeURIComponent(query)}${filters.approved ? `&approved=${filters.approved}` : ""}${filters.knowledge_id ? `&career_id=${filters.knowledge_id}` : ""}`,
    { items: [], total: 0 },
    ["career"],
  );
  const [editing, setEditing] = useState<Claim | "new" | null>(null);
  return (
    <section className="card" aria-label="All claims">
      <RecordFilters filters={filters} onChange={onChange}>
        <select
          className="input"
          aria-label="Approval"
          value={filters.approved}
          onChange={(event) =>
            onChange({ approved: event.target.value, offset: "0" })
          }
        >
          <option value="">All claims</option>
          <option value="true">Approved</option>
          <option value="false">Not approved</option>
        </select>
        <select
          className="input"
          aria-label="Entry"
          value={filters.knowledge_id}
          onChange={(event) =>
            onChange({ knowledge_id: event.target.value, offset: "0" })
          }
        >
          <option value="">All entries</option>
          {entries.map((entry) => (
            <option key={entry.id} value={entry.id}>
              {careerEntryLabel(entry)}
            </option>
          ))}
        </select>
      </RecordFilters>
      {error ? (
        <div className="body">
          <ErrorBanner message={error} retry={reload} />
        </div>
      ) : loading || filters.q !== query ? (
        <Loading label="Loading claims…" />
      ) : data.items.length ? (
        <div className="claims">
          {data.items.map((claim) => (
            <ClaimRow
              key={claim.id}
              claim={claim}
              showEntry
              onEdit={setEditing}
              onSaved={(saved) => setData(replaced(saved))}
            />
          ))}
        </div>
      ) : (
        <EmptyState title="No claim matches">
          Claims are added inside the entry they belong to.
        </EmptyState>
      )}
      <Pager
        label="Claim pages"
        offset={Number(filters.offset) || 0}
        total={data.total}
        onChange={(offset) => onChange({ offset: String(offset) })}
      />
      {editing && editing !== "new" && (
        <ClaimDialog
          record={editing}
          entries={entries}
          onClose={() => setEditing(null)}
        />
      )}
    </section>
  );
}
