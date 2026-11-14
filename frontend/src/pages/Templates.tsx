import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CircleAlert,
  FilePlus2,
  Files,
  Mail,
  Plus,
  Upload,
} from "lucide-react";
import {
  Button,
  IconButton,
  formatDate,
  List,
  ListGroup,
  ListRow,
  Callout,
  EmptyState,
  PageHeader,
  SkeletonRows,
  LeaveDialog,
  useUnloadGuard,
  SplitPane,
  useToast,
  type MenuEntry,
} from "../ui";
import { SheetMenu } from "../ui/ActionSheet";
import { TopBarActions } from "../shell/context";
import { addLeaveGuard, href, navigate, useRoute } from "../shell/router";
import {
  useCreateTemplate,
  useTemplates,
  type NewTemplate,
  type Template,
} from "../query/templates";
import { TemplateDetail } from "./templates/Detail";
import { DefaultMark } from "./templates/Mark";
import {
  KINDS,
  changedText,
  kindOfFile,
  nameOfFile,
  tabOf,
  type Tab,
} from "./templates/model";
import { EXAMPLE_CV, EXAMPLE_LETTER } from "./templates/starters";
import "./templates/templates.css";

const byDefaultThenName = (a: Template, b: Template) =>
  Number(b.is_default) - Number(a.is_default) ||
  a.name.localeCompare(b.name, "en", { numeric: true });

/** Create a template from an example or an uploaded .tex file. */
function useStart(onCreated: (template: Template) => void) {
  const create = useCreateTemplate();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const start = (body: NewTemplate) =>
    create.mutate(
      { ...body, idempotency_key: crypto.randomUUID?.() },
      {
        onSuccess: (template) => {
          toast.show({
            tone: "success",
            message: `Created “${template.name}”`,
          });
          onCreated(template);
        },
        onError: (cause) =>
          toast.show({
            tone: "error",
            message:
              cause instanceof Error
                ? cause.message
                : "The template was not created.",
          }),
      },
    );
  const picker = (
    <input
      ref={input}
      type="file"
      accept=".tex,.ltx,text/x-tex,application/x-tex"
      hidden
      aria-label="A .tex file to start from"
      onChange={async (event) => {
        const file = event.target.files?.[0];
        event.target.value = "";
        if (!file) return;
        if (file.size > 1_000_000)
          return toast.show({
            tone: "error",
            message: "Use a .tex file smaller than 1 MB.",
          });
        start({
          name: nameOfFile(file.name),
          kind: kindOfFile(file.name),
          tex: await file.text(),
          guidance: "",
          is_default: false,
        });
      }}
    />
  );
  return {
    picker,
    busy: create.isPending,
    exampleCv: () => start(EXAMPLE_CV),
    exampleLetter: () => start(EXAMPLE_LETTER),
    upload: () => input.current?.click(),
  };
}

/**
 * Templates: the designs CVs and letters are built from. A list grouped by
 * kind beside the selected template, each scrolling on its own.
 */
export default function TemplatesScreen() {
  const route = useRoute();
  const param = route.query.get("template");
  const tab = tabOf(route.query.get("tab"));
  const list = useTemplates();
  const items = useMemo(
    () => [...(list.data?.items ?? [])].sort(byDefaultThenName),
    [list.data],
  );
  const groups = KINDS.map((group) => ({
    ...group,
    rows: items.filter(
      (item) => (item.kind === "letter" ? "letter" : "cv") === group.kind,
    ),
  })).filter((group) => group.rows.length);
  const ordered = groups.flatMap((group) => group.rows);
  const selected =
    ordered.find((item) => item.id === param) ??
    (param ? null : ordered[0]) ??
    null;
  const go = useCallback(
    (template: string | null, next: Tab | null = null) =>
      navigate(
        href(
          "templates",
          {},
          {
            template: template ?? undefined,
            tab: template && next && next !== "preview" ? next : undefined,
          },
        ),
        { replace: true },
      ),
    [],
  );
  const start = useStart((template) => go(template.id, "source"));

  // Unsaved source or limits ask before the template or the page changes.
  const [dirty, setDirty] = useState(false);
  const [leaving, setLeaving] = useState<null | (() => void)>(null);
  useUnloadGuard(dirty);
  useEffect(() => {
    if (!dirty) return;
    return addLeaveGuard((proceed) => {
      setLeaving(() => proceed);
      return false;
    });
  }, [dirty]);

  const newMenu: MenuEntry[] = [
    {
      id: "cv",
      label: "Start from the example CV",
      icon: FilePlus2,
      onSelect: start.exampleCv,
    },
    {
      id: "letter",
      label: "Start from the example letter",
      icon: Mail,
      onSelect: start.exampleLetter,
    },
    "separator",
    {
      id: "upload",
      label: "Upload a .tex file…",
      icon: Upload,
      onSelect: start.upload,
    },
  ];
  const empty = list.isSuccess && !items.length;
  const newButton = !empty && (
    <SheetMenu
      label="New template"
      items={newMenu}
      trigger={(props) => (
        <Button {...props} icon={Plus} disabled={start.busy}>
          New template
        </Button>
      )}
    />
  );

  return (
    <div className="tpl-screen">
      {start.picker}
      <PageHeader title="Templates" action={newButton} />
      {!empty && (
        <TopBarActions>
          <SheetMenu
            label="New template"
            items={newMenu}
            trigger={(props) => (
              <IconButton
                {...props}
                icon={Plus}
                label="New template"
                size="touch"
                tooltip="none"
              />
            )}
          />
        </TopBarActions>
      )}
      <p className="tpl-note">
        Writing rules live in <a href="#preferences">Preferences</a>.
      </p>
      {list.isError && !list.data ? (
        <div className="tpl-state">
          <Callout
            icon={CircleAlert}
            tone="danger"
            title="Templates could not be loaded"
            actions={
              <Button size="sm" onClick={() => void list.refetch()}>
                Try again
              </Button>
            }
          />
        </div>
      ) : list.isPending ? (
        <div className="tpl-state">
          <SkeletonRows rows={6} />
        </div>
      ) : empty ? (
        <EmptyState
          icon={Files}
          title="No templates yet."
          className="tpl-empty"
          actions={
            <>
              <Button
                variant="primary"
                icon={FilePlus2}
                disabled={start.busy}
                onClick={start.exampleCv}
              >
                Start from the example CV
              </Button>
              <Button
                icon={Upload}
                disabled={start.busy}
                onClick={start.upload}
              >
                Upload a .tex file
              </Button>
              <Button
                variant="ghost"
                disabled={start.busy}
                onClick={start.exampleLetter}
              >
                Start from the example letter
              </Button>
            </>
          }
        >
          A template is the LaTeX design your CV or letter is built from.
        </EmptyState>
      ) : (
        <SplitPane
          label={selected ? selected.name : "Template"}
          open={!!param && !!selected}
          onClose={() => go(null)}
          list={
            <List
              label="Templates"
              activeId={selected?.id ?? null}
              onActiveChange={(id) => go(id, tab)}
              onOpen={(id) => go(id, tab)}
            >
              {groups.map((group) => (
                <ListGroup
                  key={group.kind}
                  label={group.label}
                  count={group.rows.length}
                >
                  {group.rows.map((item) => (
                    <ListRow
                      key={item.id}
                      id={item.id}
                      title={item.name}
                      sub={changedText(formatDate(item.updated_at))}
                      meta={item.is_default ? <DefaultMark /> : undefined}
                    />
                  ))}
                </ListGroup>
              ))}
            </List>
          }
          detail={
            selected ? (
              <TemplateDetail
                key={selected.id}
                id={selected.id}
                summary={selected}
                names={items.map((item) => item.name)}
                tab={tab}
                onTab={(next) => go(selected.id, next)}
                onBack={() => go(null)}
                onSelect={(id) => go(id)}
                onDirty={setDirty}
              />
            ) : (
              <EmptyState icon={Files} title="This template no longer exists">
                Choose another one from the list.
              </EmptyState>
            )
          }
        />
      )}
      <LeaveDialog
        open={leaving !== null}
        changes={1}
        onStay={() => setLeaving(null)}
        onLeave={() => {
          const proceed = leaving;
          setLeaving(null);
          setDirty(false);
          proceed?.();
        }}
      />
    </div>
  );
}
