import { useState } from "react";
import {
  ApiError,
  api,
  formatTime,
  policySections,
  type Policy,
  type PolicySection,
} from "../api";
import { ActorChip, Card, ErrorBanner, Loading, Split, Tag } from "../design";
import { PageHead, plural } from "../library/common";
import { useFresh } from "../library/useFresh";
import { useWorkspace } from "../state";
import { SectionCard, type Run } from "./policy/Section";

/** What a section's row in the side panel says after its name. */
function SectionState({ section }: { section: PolicySection }) {
  const unsorted = section.items.filter(
    (item) => !item.confirmed && item.origin,
  ).length;
  const proposed = section.unconfirmed - unsorted;
  if (unsorted) return <Tag tone="attention">{unsorted} unsorted</Tag>;
  return (
    <span className="caption num">
      {plural(section.total, "item")}
      {proposed ? ` · ${proposed} proposed` : ""}
    </span>
  );
}

export default function PolicyPage() {
  const { data, setData, loading, error, reload } = useFresh<Policy | null>(
    "/policy",
    null,
    ["policy"],
  );
  const { notify } = useWorkspace();
  const [busy, setBusy] = useState(false);
  const run: Run = async (call, message, form = false) => {
    setBusy(true);
    try {
      const result = (await call()) as {
        section?: PolicySection;
        from?: PolicySection;
      };
      // The answer carries the sections the write changed.
      setData(
        (current) =>
          current && {
            ...current,
            sections: current.sections.map((section) =>
              result.section?.section === section.section
                ? result.section
                : result.from?.section === section.section
                  ? result.from
                  : section,
            ),
          },
      );
      notify(message);
      return "ok";
    } catch (cause) {
      if (cause instanceof ApiError && cause.code === "conflict") {
        // Show what the other session wrote; an open form keeps its text.
        try {
          setData(await api<Policy>("/policy"));
        } catch {
          reload();
        }
        // A form says so beside the text it kept.
        if (!form)
          notify(
            "This section changed in another session. The latest version is shown; check it and try again.",
            true,
          );
        return "conflict";
      }
      notify(
        cause instanceof Error ? cause.message : "The change was not saved.",
        true,
      );
      return "error";
    } finally {
      setBusy(false);
    }
  };
  const latest = data?.sections
    .filter((section) => section.updated_at)
    .sort((a, b) => (a.updated_at! < b.updated_at! ? 1 : -1))[0];
  return (
    <>
      <PageHead title="Policy">
        What you have decided once, in your own words. Your agent follows these
        statements when it triages jobs and writes documents, and asks you when
        they do not cover a case.
      </PageHead>
      {error ? (
        <ErrorBanner message={error} retry={reload} />
      ) : loading || !data ? (
        <Loading label="Loading the policy…" />
      ) : (
        <Split columns="minmax(0, 2.2fr) minmax(0, 1fr)">
          <div className="stack">
            {data.sections.map((section) => (
              <SectionCard
                key={section.section}
                section={section}
                policy={data}
                busy={busy}
                run={run}
              />
            ))}
          </div>
          <aside className="stack detail" aria-label="About the policy">
            <Card title="Sections" className="section-nav">
              {data.sections.map((section) => (
                <button
                  type="button"
                  key={section.section}
                  onClick={() => {
                    const heading = document.getElementById(
                      `policy-${section.section}`,
                    );
                    heading?.scrollIntoView({ block: "start" });
                    heading?.focus({ preventScroll: true });
                  }}
                >
                  <span>{policySections[section.section]}</span>
                  <SectionState section={section} />
                </button>
              ))}
            </Card>
            <Card title="How it is used">
              <div className="body stack">
                <p>
                  Each section has its own version. An application records the
                  versions it was prepared under, so a change to Decision never
                  touches what a letter was written from.
                </p>
                <p>
                  Your agent may propose an item or change one. It counts only
                  after you confirm it here, and a rule on a signal stays off
                  until you turn it on.
                </p>
                {latest && (
                  <p className="caption">
                    Last change: {formatTime(latest.updated_at!)},{" "}
                    {policySections[latest.section]}, by{" "}
                    <ActorChip actor={latest.updated_by} />
                  </p>
                )}
              </div>
            </Card>
          </aside>
        </Split>
      )}
    </>
  );
}
