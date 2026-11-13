import { useState } from "react";
import { type ListResult, type Template } from "../api";
import {
  Button,
  EmptyState,
  ErrorBanner,
  Loading,
  Split,
  Tag,
} from "../design";
import { PageHead, plural } from "../library/common";
import { useFresh } from "../library/useFresh";
import {
  confirmLeave,
  useDebounce,
  useEditorRecord,
  useResource,
  useUrlFilters,
} from "../state";
import { TemplateDetail } from "./templates/Detail";
import { CreateTemplate, kindLabels } from "./templates/Dialogs";

const NONE: ListResult<Template> = { items: [], total: 0 };

export default function TemplatesPage() {
  // `template` and `section` keep the links of earlier versions working.
  const [filters, setFilters] = useUrlFilters({
    template: "",
    section: "",
    q: "",
    kind: "",
  });
  const query = useDebounce(filters.q);
  const list = useFresh(
    `/templates?summary=true&limit=200&q=${encodeURIComponent(query)}&kind=${filters.kind}`,
    NONE,
    ["templates", "files"],
  );
  const [creating, setCreating] = useState(false);
  const [pane, setPane] = useState<0 | 1>(filters.template ? 1 : 0);
  const selected = filters.template || list.data.items[0]?.id || "";
  const detail = useResource<Template | null>(
    selected ? `/templates/${selected}` : null,
    null,
  );
  const loaded = detail.data?.id === selected ? detail.data : undefined;
  const template = useEditorRecord(loaded, `/templates/${selected}`);
  const select = (id: string) => {
    if (id !== selected && !confirmLeave()) return;
    setFilters({ template: id });
    setPane(1);
  };
  const add = <Button onClick={() => setCreating(true)}>Add a template</Button>;
  const filtered = !!(query || filters.kind);
  return (
    <>
      <PageHead title="Templates" actions={add}>
        The source your CVs and letters are built from, with each one's guidance
        and limits. Your agent compiles them on its own machine; the workspace
        stores the files. Writing rules live in{" "}
        <a href="#preferences">Preferences</a>.
      </PageHead>
      {list.error ? (
        <ErrorBanner message={list.error} retry={list.reload} />
      ) : list.loading ? (
        <Loading label="Loading templates…" />
      ) : !list.data.items.length && !filtered ? (
        <section className="card">
          <EmptyState title="No template yet" action={add}>
            Add the LaTeX source of your CV or letter with its fonts and images.
            Your agent needs one template of each kind before it can prepare an
            application.
          </EmptyState>
        </section>
      ) : (
        <Split
          columns="minmax(0, 320px) minmax(0, 1fr)"
          labels={["Templates", template?.name || "Selected template"]}
          pane={pane}
          onPane={setPane}
        >
          <section className="card" aria-label="Templates by kind">
            <div className="filters" role="search">
              <input
                className="input"
                type="search"
                aria-label="Search templates"
                placeholder="Find a template"
                value={filters.q}
                onChange={(event) => setFilters({ q: event.target.value })}
              />
              <select
                className="input"
                aria-label="Kind of document"
                value={filters.kind}
                onChange={(event) => setFilters({ kind: event.target.value })}
              >
                <option value="">CV and letter</option>
                <option value="resume">CV</option>
                <option value="cover_letter">Letter</option>
              </select>
            </div>
            {!list.data.items.length && (
              <p className="body muted">No template matches.</p>
            )}
            {(["resume", "cover_letter"] as const)
              .filter((kind) =>
                list.data.items.some((item) => item.kind === kind),
              )
              .map((kind) => (
                <div key={kind}>
                  <h2 className="kind eyebrow">{kindLabels[kind]}</h2>
                  <ul className="list">
                    {list.data.items
                      .filter((item) => item.kind === kind)
                      .map((item) => (
                        <li
                          key={item.id}
                          className={
                            item.id === selected ? "is-selected" : undefined
                          }
                        >
                          <div className="grow">
                            <button
                              type="button"
                              className="title"
                              aria-current={item.id === selected || undefined}
                              onClick={() => select(item.id)}
                            >
                              {item.name}
                            </button>
                            <div className="meta">
                              Version {item.version} ·{" "}
                              {plural(item.file_count ?? 0, "asset")}
                            </div>
                          </div>
                          {item.is_default && <Tag tone="ready">Default</Tag>}
                        </li>
                      ))}
                  </ul>
                </div>
              ))}
          </section>
          {detail.error ? (
            <ErrorBanner message={detail.error} retry={detail.reload} />
          ) : template ? (
            <TemplateDetail
              template={template}
              tab={filters.section}
              onTab={(section) => setFilters({ section })}
              onRemoved={() => {
                setFilters({ template: "" });
                setPane(0);
              }}
            />
          ) : (
            <section className="card detail">
              {selected ? (
                <Loading label="Loading the template…" />
              ) : (
                <EmptyState title="No template selected">
                  Choose a template to see its source, rules and assets.
                </EmptyState>
              )}
            </section>
          )}
        </Split>
      )}
      {creating && (
        <CreateTemplate
          onClose={() => setCreating(false)}
          onCreated={(id) => {
            setCreating(false);
            setFilters({ template: id, q: "", kind: "" });
            setPane(1);
          }}
        />
      )}
    </>
  );
}
