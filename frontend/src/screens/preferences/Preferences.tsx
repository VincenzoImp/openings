import { useCallback, useEffect, useState } from "react";
import {
  PageHeader,
  SkeletonRows,
  LeaveDialog,
  useUnloadGuard,
  useToast,
} from "../../ui";
import { addLeaveGuard } from "../../shell/router";
import {
  usePreferences,
  type SectionName,
  type Statement,
} from "../../query/preferences";
import {
  SECTIONS,
  itemName,
  placeOf,
  removed,
  reordered,
  saved,
  sectionTitle,
} from "./model";
import { PreferenceSection, type SectionActions } from "./Section";
import { FollowingUp, Languages } from "./Settings";
import { useStatements } from "./useStatements";
import "./preferences.css";
import { LoadError } from "../../ui/LoadError";

/**
 * Preferences: in the owner's words, what they want, rule out and are, how
 * their documents are written and how to work with them; then the no-reply
 * period. Statements are lines of text, edited in place.
 */
export default function PreferencesScreen() {
  const query = usePreferences();
  const statements = useStatements(query.data?.sections);
  const toast = useToast();
  const [dirty, setDirty] = useState<ReadonlySet<SectionName>>(() => new Set());
  const [leaving, setLeaving] = useState<null | (() => void)>(null);
  const unsaved = dirty.size > 0;
  useUnloadGuard(unsaved);
  useEffect(() => {
    if (!unsaved) return;
    return addLeaveGuard((proceed) => {
      setLeaving(() => proceed);
      return false;
    });
  }, [unsaved]);
  const markDirty = useCallback((name: SectionName, value: boolean) => {
    setDirty((current) => {
      if (current.has(name) === value) return current;
      const next = new Set(current);
      if (value) next.add(name);
      else next.delete(name);
      return next;
    });
  }, []);
  const { change, itemsOf, error, clearError } = statements;
  useEffect(() => {
    if (!error) return;
    toast.show({ tone: "error", message: error });
    clearError();
  }, [error, toast, clearError]);

  function actionsOf(name: SectionName): SectionActions {
    const writing = name === "writing";
    const clean = (item: Statement): Statement =>
      writing
        ? { text: item.text, scope: item.scope || "all" }
        : { text: item.text };
    return {
      save: async (index, original, draft) =>
        (await change(name, (items) =>
          saved(items, clean(draft), index ?? -1, original),
        )) === "ok",
      remove: (index) => {
        const item = itemsOf(name)[index];
        if (!item) return;
        void change(name, (items) => removed(items, index, item.text)).then(
          (outcome) => {
            if (outcome !== "ok") return;
            toast.show({
              message: `Deleted “${itemName(item.text, 32)}”`,
              action: {
                label: "Undo",
                undo: true,
                run: () =>
                  void change(name, (items) => [
                    ...items.slice(0, index),
                    item,
                    ...items.slice(index),
                  ]),
              },
            });
          },
        );
      },
      move: async (index, to) => {
        const item = itemsOf(name)[index];
        if (!item) return;
        const moved: Statement =
          to === "writing"
            ? { text: item.text, scope: "all" }
            : { text: item.text };
        if ((await change(to, (items) => [...items, moved])) !== "ok") return;
        if (
          (await change(name, (items) => removed(items, index, item.text))) !==
          "ok"
        )
          return;
        toast.show({
          message: `Moved “${itemName(item.text, 28)}” to ${sectionTitle(to)}`,
        });
      },
      reorder: (from, to) => {
        const item = itemsOf(name)[from];
        if (!item) return;
        void change(name, (items) => {
          const at = placeOf(items, from, item.text);
          return at < 0 ? items : reordered(items, at, to);
        });
      },
    };
  }

  const settings = query.data?.settings;
  return (
    <div className="prefs">
      <PageHeader title="Preferences" />
      {query.isError && !query.data ? (
        <div className="prefs-state">
          <LoadError
            what="your preferences"
            error={query.error}
            retry={() => void query.refetch()}
          />
        </div>
      ) : !query.data || !settings ? (
        <div className="prefs-state">
          <SkeletonRows rows={8} />
        </div>
      ) : (
        <div className="prefs-doc">
          {SECTIONS.map((info) => (
            <PreferenceSection
              key={info.name}
              info={info}
              items={itemsOf(info.name)}
              conflict={statements.conflicts.has(info.name)}
              actions={actionsOf(info.name)}
              onDirty={(value) => markDirty(info.name, value)}
              onReload={() => {
                statements.settle(info.name);
                markDirty(info.name, false);
                void query.refetch();
              }}
              onKeepEditing={() => {
                statements.settle(info.name);
                void query.refetch();
              }}
            >
              {info.name === "facts" && <Languages settings={settings} />}
            </PreferenceSection>
          ))}
          <FollowingUp settings={settings} />
        </div>
      )}
      <LeaveDialog
        open={leaving !== null}
        changes={dirty.size}
        onStay={() => setLeaving(null)}
        onLeave={() => {
          const proceed = leaving;
          setLeaving(null);
          setDirty(new Set());
          proceed?.();
        }}
      />
    </div>
  );
}
