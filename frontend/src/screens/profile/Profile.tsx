// Profile (#profile): the career record read as a finished CV. Header,
// summary, Experience, Education, Projects, Other and the skills of the
// whole record; one block is changed on purpose (Edit → Save or Cancel).
// Desktop has an "On this page" rail; a phone has a Jump to menu.
import { useState, type ReactNode } from "react";
import { List, Plus, Upload, UserRound } from "lucide-react";
import { Button, IconButton } from "../../ui/Button";
import { Menu } from "../../ui/Menu";
import { EmptyState, PageHeader, Skeleton } from "../../ui/Page";
import { Tag } from "../../ui/Badge";
import { TopBarActions } from "../../shell/context";
import { EditingProvider, useEditing } from "./Block";
import {
  useEntries,
  useEntryFiles,
  useHighlights,
  useProfile,
  type Entry,
  type EntryFile,
  type Highlight,
} from "./data";
import { EntryBlock, EntryForm } from "./Entry";
import { HeaderBlock, SummaryBlock } from "./Header";
import { ImportDialog } from "./ImportDialog";
import { SECTIONS, allSkills, sectionOf } from "./model";
import "./profile.css";
import { LoadError } from "../../ui/LoadError";

const SHOWN = 8;

export default function ProfilePage() {
  return (
    <EditingProvider>
      <ProfileScreen />
    </EditingProvider>
  );
}

/** Group by a key, keeping the order. */
function groups<T>(items: T[], key: (item: T) => string) {
  const map = new Map<string, T[]>();
  for (const item of items)
    map.set(key(item), [...(map.get(key(item)) ?? []), item]);
  return map;
}
const byPosition = <T extends { position: number }>(items: T[] = []) =>
  [...items].sort((a, b) => a.position - b.position);

function ProfileScreen() {
  const profile = useProfile();
  const entries = useEntries();
  const highlights = useHighlights();
  const files = useEntryFiles();
  const editing = useEditing();
  const [importing, setImporting] = useState(false);
  const queries = [profile, entries, highlights];
  const loading = queries.some((query) => query.isPending);
  const failed = queries.find((query) => query.error)?.error;
  const p = profile.data;
  const list = byPosition(entries.data);
  const skills = allSkills(list);
  const bySection = groups(list, (entry) => sectionOf(entry.kind));
  const empty =
    !list.length &&
    !p?.name.trim() &&
    !p?.headline.trim() &&
    !p?.summary.trim();
  const shown = SECTIONS.filter(
    (section) =>
      section.id !== "other" ||
      bySection.has("other") ||
      editing.open === "new:other",
  );
  const rail = [
    { id: "header", title: p?.name.trim() || "Contact" },
    { id: "summary", title: "Summary" },
    ...shown,
    ...(skills.length ? [{ id: "skills", title: "Skills" }] : []),
  ];
  const ready = !loading && !failed && (!empty || editing.open);
  const open = () => setImporting(true);

  let body: ReactNode;
  if (failed)
    body = (
      <LoadError
        what="your profile"
        error={failed}
        retry={() => queries.forEach((query) => void query.refetch())}
      />
    );
  else if (loading)
    body = (
      <div className="pf-cv" role="status" aria-label="Loading">
        {[56, 14, 14, 14].map((height, index) => (
          <div className="pf-skel" key={index}>
            <Skeleton
              width={height > 20 ? 260 : 140}
              height={height > 20 ? 28 : 14}
            />
            <Skeleton width="72%" height={12} />
            <Skeleton width="88%" height={12} />
          </div>
        ))}
      </div>
    );
  else if (!ready)
    body = (
      <EmptyState
        icon={UserRound}
        title="Your profile is empty."
        className="pf-empty"
        actions={
          <>
            <Button variant="primary" icon={Upload} onClick={open}>
              Import CV text
            </Button>
            <Button variant="ghost" onClick={() => editing.request("header")}>
              Start with your name
            </Button>
          </>
        }
      >
        Paste your CV to start, or write it here block by block.
      </EmptyState>
    );
  else {
    const highlightsOf = groups(
      byPosition(highlights.data),
      (item) => item.career_id,
    );
    const filesOf = groups(files.data ?? [], (file) => file.owner_id);
    body = (
      <div className="pf-layout">
        <div className="pf-cv">
          <section id="pf-header" aria-label="Header">
            <HeaderBlock profile={p!} />
          </section>
          <Section id="summary" title="Summary">
            <SummaryBlock profile={p!} />
          </Section>
          {shown.map((section) => {
            const items = bySection.get(section.id) ?? [];
            const adding = editing.open === `new:${section.id}`;
            return (
              <Section
                key={section.id}
                id={section.id}
                title={section.title}
                count={items.length}
                action={
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={Plus}
                    onClick={() => editing.request(`new:${section.id}`)}
                  >
                    {section.add}
                  </Button>
                }
              >
                {adding && (
                  <EntryForm
                    entry={null}
                    kind={section.kind}
                    context={{ highlights: [], files: [], section: items }}
                  />
                )}
                {!items.length && !adding && (
                  <p className="pf-none">
                    No {section.title.toLowerCase()} yet.
                  </p>
                )}
                <Entries
                  entries={items}
                  showKind={
                    section.id === "other" || section.id === "education"
                  }
                  highlightsOf={highlightsOf}
                  filesOf={filesOf}
                />
              </Section>
            );
          })}
          {skills.length > 0 && (
            <Section id="skills" title="Skills">
              <div className="pf-tags">
                {skills.map((skill) => (
                  <Tag key={skill}>{skill}</Tag>
                ))}
              </div>
            </Section>
          )}
        </div>
        <nav className="pf-rail" aria-label="On this page">
          <p>On this page</p>
          {rail.map((item) => (
            <a key={item.id} href={`#pf-${item.id}`} onClick={jump(item.id)}>
              {item.title}
            </a>
          ))}
        </nav>
      </div>
    );
  }

  return (
    <div className="pf">
      <PageHeader
        title="Profile"
        action={
          ready && (
            <Button icon={Upload} onClick={open}>
              Import CV text
            </Button>
          )
        }
      />
      {ready && (
        <TopBarActions>
          <Menu
            label="Jump to"
            placement="bottom-end"
            items={rail.map((item) => ({
              id: item.id,
              label: item.title,
              onSelect: () => jump(item.id)(),
            }))}
            trigger={(props) => (
              <IconButton
                {...props}
                icon={List}
                size="touch"
                label="Jump to"
                tooltip="none"
              />
            )}
          />
          <IconButton
            icon={Upload}
            size="touch"
            label="Import CV text"
            tooltip="none"
            onClick={open}
          />
        </TopBarActions>
      )}
      <div className="pf-body">{body}</div>
      <ImportDialog open={importing} onClose={() => setImporting(false)} />
    </div>
  );
}

/** Scroll to a section and move focus to its heading. */
const jump = (id: string) => (event?: { preventDefault: () => void }) => {
  event?.preventDefault();
  const target = document.getElementById(`pf-${id}`);
  target?.scrollIntoView({ block: "start" });
  target
    ?.querySelector<HTMLElement>("h2, .pf-block")
    ?.focus({ preventScroll: true });
};

function Section({
  id,
  title,
  count,
  action,
  children,
}: {
  id: string;
  title: string;
  count?: number;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={`pf-${id}`} aria-labelledby={`pf-${id}-h`}>
      <div className="pf-section-head">
        <h2 id={`pf-${id}-h`} tabIndex={-1}>
          {title}
          {!!count && <span className="pf-count">{count}</span>}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

/** The entries of a section; a long one shows its first eight, then all. */
function Entries({
  entries,
  showKind,
  highlightsOf,
  filesOf,
}: {
  entries: Entry[];
  showKind: boolean;
  highlightsOf: Map<string, Highlight[]>;
  filesOf: Map<string, EntryFile[]>;
}) {
  const editing = useEditing();
  const [all, setAll] = useState(false);
  const limit =
    all || entries.findIndex((entry) => entry.id === editing.open) >= SHOWN
      ? entries.length
      : SHOWN;
  return (
    <>
      {entries.slice(0, limit).map((entry) => (
        <EntryBlock
          key={entry.id}
          entry={entry}
          showKind={showKind}
          context={{
            highlights: highlightsOf.get(entry.id) ?? [],
            files: filesOf.get(entry.id) ?? [],
            section: entries,
          }}
        />
      ))}
      {entries.length > limit && (
        <Button
          variant="ghost"
          size="sm"
          className="pf-show-all"
          onClick={() => setAll(true)}
        >
          Show all {entries.length}
        </Button>
      )}
    </>
  );
}
