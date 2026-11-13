import { useRef, useState } from "react";
import {
  Card,
  EmptyState,
  ErrorBanner,
  ListRow,
  Loading,
  Split,
  Tag,
} from "../../design";
import { plural } from "../../library/common";
import { useFresh } from "../../library/useFresh";
import { confirmLeave, useUrlState } from "../../state";
import type { SkillItem } from "./model";
import { SkillDetail } from "./SkillDetail";

const NONE: { items: SkillItem[] } = { items: [] };

/**
 * The skills the workspace serves to agents, beside the one opened: its text,
 * reference files and local notes. `skill=` opens one; `from_run=` offers a
 * run's method section as a local note.
 */
export function Skills({ release }: { release?: string }) {
  const list = useFresh("/skills", NONE, ["skills"]);
  const [skill, setSkill] = useUrlState("skill", "");
  const [pane, setPane] = useState<0 | 1>(skill ? 1 : 0);
  const opened = useRef(false);
  const items = list.data.items;
  const selected = items.find((item) => item.name === skill) || items[0];
  if (list.error)
    return <ErrorBanner message={list.error} retry={list.reload} />;
  if (list.loading) return <Loading label="Loading skills…" />;
  if (!items.length)
    return (
      <Card>
        <EmptyState title="No skill is served">
          This installation was started without its skills directory.
        </EmptyState>
      </Card>
    );
  return (
    <Split
      columns="minmax(0, 340px) minmax(0, 1fr)"
      labels={["Skills", selected?.name || "Skill"]}
      pane={pane}
      onPane={setPane}
    >
      <section className="card" aria-label="Skills served to your agent">
        <header>
          <p className="grow muted">
            {plural(items.length, "skill")}
            {release ? `, shipped with version ${release}` : ""}. They cannot be
            edited; add local notes instead.
          </p>
        </header>
        <ul className="list skills" aria-label="Skills">
          {items.map((item) => (
            <ListRow
              key={item.name}
              title={item.name}
              meta={item.description}
              selected={item.name === selected?.name}
              onOpen={() => {
                if (item.name !== selected?.name && !confirmLeave()) return;
                opened.current = true;
                setSkill(item.name);
                setPane(1);
              }}
            >
              {item.local_notes && <Tag tone="ready">Local notes</Tag>}
            </ListRow>
          ))}
        </ul>
      </section>
      {selected && (
        <SkillDetail
          key={selected.name}
          skill={selected}
          release={release}
          focus={opened.current}
        />
      )}
    </Split>
  );
}
