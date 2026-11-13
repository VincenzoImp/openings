import { useState } from "react";
import {
  ApiError,
  api,
  type PreferenceSection,
  type Preferences,
  type WorkspaceSettings,
} from "../api";
import { Card, ErrorBanner, Loading, Split } from "../design";
import { PageHead, plural } from "../library/common";
import { useFresh } from "../library/useFresh";
import { useWorkspace } from "../state";
import { itemsBody } from "./preferences/model";
import { SectionCard, type Outcome, type Save } from "./preferences/Section";
import { FactSettings, type SaveSettings } from "./preferences/Settings";

const CHANGED =
  "Preferences changed in another session. The latest version is shown; check it and try again.";

export default function PreferencesPage() {
  const { data, setData, loading, error, reload } =
    useFresh<Preferences | null>("/preferences", null, [
      "preferences",
      "settings",
    ]);
  const { notify } = useWorkspace();
  const [busy, setBusy] = useState(false);
  /** Send one write; a conflict reads Preferences again and says so. */
  async function write<T>(
    call: () => Promise<T>,
    apply: (result: T) => void,
    message: string,
    form = false,
  ): Promise<Outcome> {
    setBusy(true);
    try {
      apply(await call());
      notify(message);
      return "ok";
    } catch (cause) {
      if (cause instanceof ApiError && cause.code === "conflict") {
        // Show what the other session wrote; an open form keeps its text.
        try {
          setData(await api<Preferences>("/preferences"));
        } catch {
          reload();
        }
        // A form says so beside the text it kept.
        if (!form) notify(CHANGED, true);
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
  }
  const save: Save = (section, items, message, form) =>
    write(
      () =>
        api<PreferenceSection>(`/preferences/${section.section}`, "PUT", {
          expected_version: section.version,
          items: itemsBody(section.section, items),
        }),
      (result) =>
        setData(
          (current) =>
            current && {
              ...current,
              sections: current.sections.map((entry) =>
                entry.section === result.section ? result : entry,
              ),
            },
        ),
      message,
      form,
    );
  const saveSettings: SaveSettings = (patch, message) =>
    write(
      () =>
        api<WorkspaceSettings>("/settings", "PATCH", {
          expected_version: data!.settings.version,
          ...patch,
        }),
      (settings) => setData((current) => current && { ...current, settings }),
      message,
    );
  return (
    <>
      <PageHead title="Preferences">
        What you want, in your own words. Your agent reads these statements when
        it reviews jobs and writes documents, and asks you when they do not
        cover a case. Nothing here acts on its own.
      </PageHead>
      {error ? (
        <ErrorBanner message={error} retry={reload} />
      ) : loading || !data ? (
        <Loading label="Loading your preferences…" />
      ) : (
        <Split columns="minmax(0, 2.2fr) minmax(0, 1fr)">
          <div className="stack">
            {data.sections.map((section) => (
              <SectionCard
                key={section.section}
                section={section}
                busy={busy}
                save={save}
              >
                {section.section === "facts" && (
                  <FactSettings
                    settings={data.settings}
                    busy={busy}
                    save={saveSettings}
                  />
                )}
              </SectionCard>
            ))}
          </div>
          <aside className="stack detail" aria-label="About Preferences">
            <Card title="Sections" className="section-nav">
              {data.sections.map((section) => (
                <button
                  type="button"
                  key={section.section}
                  onClick={() => {
                    const heading = document.getElementById(
                      `preferences-${section.section}`,
                    );
                    heading?.scrollIntoView({ block: "start" });
                    heading?.focus({ preventScroll: true });
                  }}
                >
                  <span>{section.title}</span>
                  <span className="caption num">
                    {plural(section.items.length, "statement")}
                  </span>
                </button>
              ))}
            </Card>
            <Card title="How it is used">
              <div className="body stack">
                <p>
                  An application keeps a copy of your facts and writing rules as
                  they were when its documents were prepared, so a later change
                  shows there as an input that changed.
                </p>
                <p>
                  Your agent may add or change a statement when you ask it to.
                  Jobs are never dismissed automatically: Jobs can hide the ones
                  requiring a language you do not speak.
                </p>
              </div>
            </Card>
          </aside>
        </Split>
      )}
    </>
  );
}
