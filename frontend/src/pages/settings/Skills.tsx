import { Card, EmptyState, ErrorBanner, Loading } from "../../design";
import { useFresh } from "../../library/useFresh";
import type { SkillItem } from "./model";

const NONE: { items: SkillItem[] } = { items: [] };

/**
 * What the skills shipped with this version let the owner ask their agent:
 * for each, a plain title, one sentence and an example to say in the agent's
 * chat. Read-only: the skills themselves are served to the agent unchanged.
 */
export function Skills({ release }: { release?: string }) {
  const list = useFresh("/skills", NONE, ["skills"]);
  const items = list.data.items;
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
    <section className="card" aria-labelledby="skills-title">
      <header>
        <h2 id="skills-title" className="grow">
          What you can ask your agent
        </h2>
      </header>
      <div className="body">
        <p className="muted">
          Your agent works in this workspace when you ask it in its own chat.
          These are the kinds of work its skills
          {release ? `, shipped with version ${release},` : ""} cover; say it in
          your own words.
        </p>
      </div>
      <ul className="list skills" aria-label="What you can ask your agent">
        {items.map((item) => (
          <li key={item.name}>
            <div className="grow">
              <h3 className="title">{item.title || item.name}</h3>
              <p className="meta">{item.summary || item.description}</p>
              {item.example && (
                <p className="caption example">
                  For example: <q>{item.example}</q>
                </p>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
