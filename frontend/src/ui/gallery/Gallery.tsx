import { useEffect, useState, type ReactNode } from "react";
import {
  Bookmark,
  CircleHelp,
  Copy,
  Ellipsis,
  ExternalLink,
  EyeOff,
  Files,
  Globe,
  Inbox,
  Layers,
  Monitor,
  Moon,
  NotebookPen,
  Pencil,
  Plus,
  Search,
  Sun,
  Trash2,
} from "lucide-react";
import {
  Avatar,
  BrandMark,
  Button,
  Checkbox,
  ConfirmDialog,
  Count,
  Dialog,
  DialogPreview,
  Dot,
  Drawer,
  EmptyState,
  Field,
  FilterChips,
  formatDate,
  formatNumber,
  Icon,
  IconButton,
  Input,
  Kbd,
  Menu,
  MenuPreview,
  NeedsCount,
  PageHeader,
  Popover,
  Segmented,
  Select,
  SkeletonRows,
  Status,
  STAGES,
  Switch,
  Table,
  Tag,
  Textarea,
  ToneText,
  ToastProvider,
  ToastView,
  useToast,
  applyTheme,
  readTheme,
  type FilterChip,
  type MenuEntry,
  type Stage,
  type ThemeMode,
} from "..";
import { NOW, PROVIDERS } from "./data";
import "./gallery.css";

/* ------------------------------------------------------------ foundations */

const SWATCHES = [
  "--bg",
  "--bg-subtle",
  "--surface",
  "--hover",
  "--selected",
  "--border",
  "--border-strong",
  "--control",
  "--text",
  "--text-2",
  "--text-3",
  "--text-disabled",
  "--primary",
  "--accent",
  "--accent-text",
  "--accent-soft",
  "--success",
  "--success-soft",
  "--warning",
  "--warning-soft",
  "--danger",
  "--danger-soft",
];

function Swatches({ theme }: { theme: ThemeMode }) {
  const [values, setValues] = useState<Record<string, string>>({});
  useEffect(() => {
    const style = getComputedStyle(document.documentElement);
    setValues(
      Object.fromEntries(
        SWATCHES.map((name) => [name, style.getPropertyValue(name).trim()]),
      ),
    );
  }, [theme]);
  return (
    <ul className="gx-swatches">
      {SWATCHES.map((name) => (
        <li key={name} className="gx-swatch">
          <span
            className="gx-swatch-fill"
            style={{ background: `var(${name})` }}
          />
          <span className="gx-swatch-name">{name.slice(2)}</span>
          <code>{values[name] || " "}</code>
        </li>
      ))}
    </ul>
  );
}

const TYPE = [
  ["3xl", "28/34 600", "Good afternoon, Alex"],
  ["2xl", "22/28 600", "Data Engineer, Grid Platform"],
  ["xl", "18/26 600", "Ready to apply"],
  ["lg", "16/24 400", "Posting and long-form reading text."],
  ["md", "14/20 400–500", "Default interface text. Row titles at 500."],
  ["sm", "13/18 400–500", "Meta, buttons, navigation, table cells"],
  ["xs", "12/16 500", "Group labels, counters, captions"],
] as const;

function TypeScale() {
  return (
    <div className="gx-type">
      {TYPE.map(([size, spec, sample]) => (
        <div key={size} className="gx-type-row">
          <code>
            {size} {spec}
          </code>
          <span className="gx-type-sample" data-size={size}>
            {sample}
          </span>
        </div>
      ))}
    </div>
  );
}

function Scales() {
  return (
    <div className="gx-scales">
      <h3 className="gx-cell-title">
        Spacing <span>4 px grid</span>
      </h3>
      <div className="gx-scale">
        {[4, 8, 12, 16, 20, 24, 32, 40, 48, 64].map((n) => (
          <div key={n}>
            <i style={{ width: n, height: n }} />
            <code>{n}</code>
          </div>
        ))}
      </div>
      <h3 className="gx-cell-title">
        Radius <span>4 · 6 · 8 · 12 · full</span>
      </h3>
      <div className="gx-scale">
        {(
          [
            ["sm", "tag"],
            ["md", "control"],
            ["lg", "menu"],
            ["xl", "dialog"],
            ["full", "chip"],
          ] as const
        ).map(([radius, name]) => (
          <div key={radius}>
            <i
              className="gx-radius"
              style={{ borderRadius: `var(--r-${radius})` }}
            />
            <code>{name}</code>
          </div>
        ))}
      </div>
      <h3 className="gx-cell-title">
        Elevation <span>only for things that float</span>
      </h3>
      <div className="gx-elevation">
        {(
          [
            ["none", "flat"],
            ["xs", "xs · button"],
            ["md", "md · menu"],
            ["lg", "lg · dialog"],
          ] as const
        ).map(([level, name]) => (
          <div
            key={level}
            style={{
              boxShadow:
                level === "none"
                  ? "inset 0 0 0 1px var(--border)"
                  : `var(--shadow-${level})`,
            }}
          >
            {name}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- components */

function Cell({
  title,
  note,
  children,
  wide = false,
}: {
  title: string;
  note?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <section
      className="gx-cell"
      data-wide={wide || undefined}
      aria-label={title}
    >
      <h3 className="gx-cell-title">
        {title} {note && <span>{note}</span>}
      </h3>
      {children}
    </section>
  );
}

function Buttons() {
  return (
    <div className="gx-stack">
      <div className="gx-row">
        <Button variant="primary" kbd="⌘↵">
          Mark applied
        </Button>
        <Button>Start application</Button>
        <Button variant="ghost">Cancel</Button>
      </div>
      <div className="gx-row">
        <Button icon={Plus}>Add job</Button>
        <Button variant="ghost" icon={Pencil}>
          Edit
        </Button>
        <IconButton icon={Ellipsis} label="More actions" />
        <IconButton icon={Copy} label="Copy link" shortcut="C" />
      </div>
      <div className="gx-row">
        <Button variant="primary" size="sm">
          Small
        </Button>
        <Button size="sm">Small</Button>
        <Button variant="primary" disabled>
          Disabled
        </Button>
        <Button variant="danger" size="sm">
          Delete job
        </Button>
      </div>
    </div>
  );
}

function StatusAndCounts() {
  return (
    <div className="gx-stack">
      <div className="gx-row gx-row-loose">
        {(Object.keys(STAGES) as Stage[]).map((stage) => (
          <Status key={stage} stage={stage} />
        ))}
      </div>
      <div className="gx-row gx-row-loose">
        <span className="gx-inline">
          <NeedsCount value={7} label="ready applications" />
          <span className="gx-caption">needs you</span>
        </span>
        <span className="gx-inline">
          <Count value={11} />
          <span className="gx-caption">informational</span>
        </span>
        <span className="gx-inline">
          <Count value={25_400} />
          <span className="gx-caption">compact</span>
        </span>
      </div>
      <div className="gx-row">
        <Tag>Python</Tag>
        <Tag icon={Globe}>English</Tag>
        <ToneText tone="warning">Closes tomorrow</ToneText>
      </div>
      <div className="gx-row">
        <ToneText tone="danger">Overdue 2 days</ToneText>
        <span className="gx-inline">
          <Dot />
          <span className="gx-caption">unread</span>
        </span>
        <Avatar name="Alex Morgan" />
      </div>
    </div>
  );
}

function ViewsAndFilters() {
  const [view, setView] = useState<"all" | "open" | "closed">("all");
  const [mode, setMode] = useState<"text" | "pdf">("text");
  const [auto, setAuto] = useState(true);
  const [paused, setPaused] = useState(false);
  const [checked, setChecked] = useState(true);
  const [chips, setChips] = useState<FilterChip[]>([
    { key: "stage", field: "Stage", value: "Ready, Applied" },
  ]);
  return (
    <div className="gx-stack">
      <div className="gx-row">
        <Segmented
          label="Applications shown"
          value={view}
          onChange={setView}
          options={[
            { value: "all", label: "All" },
            { value: "open", label: "Open" },
            { value: "closed", label: "Closed" },
          ]}
        />
        <Segmented
          label="Document view"
          value={mode}
          onChange={setMode}
          options={[
            { value: "text", label: "Text", icon: Files, iconOnly: true },
            { value: "pdf", label: "PDF", icon: Layers, iconOnly: true },
          ]}
        />
      </div>
      <div className="gx-chips">
        <FilterChips
          chips={chips}
          onRemove={(key) =>
            setChips((list) => list.filter((chip) => chip.key !== key))
          }
          onClear={() => setChips([])}
        >
          <button
            type="button"
            className="ui-chip gx-chip-add"
            onClick={() =>
              setChips((list) => [
                ...list,
                { key: `l${list.length}`, field: "Language", value: "German" },
              ])
            }
          >
            <Icon icon={Plus} size="sm" />
            Filter
          </button>
        </FilterChips>
        {!chips.length && (
          <Button
            size="sm"
            variant="ghost"
            icon={Plus}
            onClick={() =>
              setChips([
                { key: "stage", field: "Stage", value: "Ready, Applied" },
              ])
            }
          >
            Filter
          </Button>
        )}
      </div>
      <div className="gx-row gx-row-loose">
        <Switch
          label="Auto-review"
          checked={auto}
          onChange={(event) => setAuto(event.target.checked)}
        />
        <Switch
          label="Paused"
          checked={paused}
          onChange={(event) => setPaused(event.target.checked)}
        />
        <Checkbox
          label="Remote"
          checked={checked}
          onChange={(event) => setChecked(event.target.checked)}
        />
        <Checkbox label="Hybrid" />
      </div>
    </div>
  );
}

const MENU: MenuEntry[] = [
  { id: "open", label: "Open posting", icon: ExternalLink },
  { id: "note", label: "Add note", icon: NotebookPen, kbd: "N" },
  { id: "copy", label: "Copy link", icon: Copy },
  { id: "dup", label: "Mark as duplicate…", icon: Layers },
  "separator",
  { id: "delete", label: "Delete job…", icon: Trash2, danger: true },
];

function Menus() {
  const toast = useToast();
  const live = MENU.map((entry) =>
    typeof entry === "object" && "id" in entry
      ? {
          ...entry,
          onSelect: () =>
            toast.show({
              message: `${entry.label.replace("…", "")} chosen`,
              tone: "success" as const,
            }),
        }
      : entry,
  );
  return (
    <div className="gx-stack">
      <MenuPreview
        label="Job actions (preview)"
        items={MENU}
        highlight="note"
      />
      <div className="gx-row">
        <Menu
          label="Job actions"
          items={live}
          trigger={(props) => (
            <Button {...props} icon={Ellipsis} variant="secondary">
              Open the menu
            </Button>
          )}
        />
        <Popover
          label="About signals"
          trigger={(props) => (
            <IconButton {...props} icon={CircleHelp} label="About signals" />
          )}
        >
          Signals are labels from the posting text: language, required
          languages, a possible duplicate. They filter; they never dismiss a
          job.
        </Popover>
      </div>
    </div>
  );
}

function Toasts() {
  const toast = useToast();
  return (
    <div className="gx-stack">
      <div className="gx-toasts">
        <ToastView
          message="Shortlisted 3 jobs"
          icon={Bookmark}
          action={{ label: "Undo", run: () => undefined, undo: true }}
        />
        <ToastView
          message="Profile saved"
          tone="success"
          onClose={() => undefined}
        />
        <ToastView
          message="Could not reach the server"
          tone="error"
          action={{ label: "Retry", run: () => undefined }}
        />
      </div>
      <div className="gx-row">
        <Button
          size="sm"
          onClick={() =>
            toast.show({
              message: "Dismissed “Backend Engineer”",
              icon: EyeOff,
              action: {
                label: "Undo",
                undo: true,
                run: () =>
                  toast.show({
                    message: "Restored “Backend Engineer”",
                    tone: "success",
                  }),
              },
            })
          }
        >
          Show undo toast
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() =>
            toast.show({
              message: "Could not reach the server",
              tone: "error",
              action: { label: "Retry", run: () => undefined },
            })
          }
        >
          Show error
        </Button>
      </div>
    </div>
  );
}

function Dialogs() {
  const [confirm, setConfirm] = useState(false);
  const [add, setAdd] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [posting, setPosting] = useState("");
  const toast = useToast();
  return (
    <div className="gx-stack">
      <DialogPreview
        title="Delete this job permanently?"
        footer={
          <>
            <Button variant="ghost">Cancel</Button>
            <Button variant="danger">Delete job</Button>
          </>
        }
      >
        Its posting, notes and timeline are removed. Dismissing keeps it
        recoverable instead.
      </DialogPreview>
      <div className="gx-row">
        <Button size="sm" onClick={() => setAdd(true)}>
          Add job…
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setConfirm(true)}>
          Delete…
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setDrawer(true)}>
          Open drawer
        </Button>
      </div>
      <ConfirmDialog
        open={confirm}
        title="Delete this job permanently?"
        confirm="Delete job"
        onConfirm={() =>
          toast.show({ message: "Deleted “Backend Engineer”", tone: "success" })
        }
        onClose={() => setConfirm(false)}
      >
        Its posting, notes and timeline are removed. Dismissing keeps it
        recoverable instead.
      </ConfirmDialog>
      <Dialog
        open={add}
        onClose={() => setAdd(false)}
        title="Add job"
        initialFocus="textarea"
        footer={
          <>
            <Button variant="ghost" onClick={() => setAdd(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              kbd="⌘↵"
              disabled={!posting.trim()}
              onClick={() => {
                setAdd(false);
                setPosting("");
                toast.show({
                  message: "Added “Data Engineer”",
                  tone: "success",
                });
              }}
            >
              Add job
            </Button>
          </>
        }
      >
        <Field
          label="Posting address or text"
          hint="We fetch the text and check for duplicates."
        >
          <Textarea
            rows={3}
            value={posting}
            onChange={(event) => setPosting(event.target.value)}
            placeholder="https://jobs.example.com/data-engineer"
          />
        </Field>
      </Dialog>
      <Drawer
        open={drawer}
        onClose={() => setDrawer(false)}
        title="Edit career entry"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDrawer(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => setDrawer(false)}>
              Save
            </Button>
          </>
        }
      >
        <Field label="Title">
          <Input defaultValue="Data engineer" />
        </Field>
        <Field label="Organisation">
          <Input defaultValue="Example Grid Services" />
        </Field>
        <Field label="Summary" optional>
          <Textarea
            rows={6}
            defaultValue="Built the meter-data ingestion platform."
          />
        </Field>
      </Drawer>
    </div>
  );
}

function Fields() {
  const [address, setAddress] = useState(
    "https://jobs.example.com/data-engineer",
  );
  const [email, setEmail] = useState("alex@example");
  const invalid = !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email);
  return (
    <div className="gx-stack gx-stack-16">
      <Field
        label="Posting address"
        hint="We fetch the text and check for duplicates."
      >
        <Input
          value={address}
          onChange={(event) => setAddress(event.target.value)}
        />
      </Field>
      <Field
        label="Email"
        error={
          invalid ? "Add the domain, for example alex@example.com" : undefined
        }
      >
        <Input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </Field>
      <Field label="Stage">
        <Select defaultValue="ready">
          {(Object.keys(STAGES) as Stage[]).map((stage) => (
            <option key={stage} value={stage}>
              {STAGES[stage]}
            </option>
          ))}
        </Select>
      </Field>
    </div>
  );
}

function Providers() {
  return (
    <Table
      caption="Providers"
      rowKey={(row) => row.name}
      rows={[...PROVIDERS]}
      columns={[
        { key: "name", label: "Provider", value: (row) => row.name },
        {
          key: "status",
          label: "Status",
          value: (row) => (
            <span className={`gx-inline ui-tone-${row.tone}`}>
              <span className="gx-dot" />
              {row.status}
            </span>
          ),
        },
        {
          key: "spacing",
          label: "Spacing",
          numeric: true,
          value: (row) => `${row.spacing} s`,
        },
        {
          key: "day",
          label: "24h",
          numeric: true,
          value: (row) => formatNumber(row.day),
        },
        { key: "note", label: "Note", value: () => null },
      ]}
    />
  );
}

function Formats() {
  const samples: [string, Date][] = [
    ["Found", new Date(NOW.getTime() - 40_000)],
    ["Found", new Date(NOW.getTime() - 25 * 60_000)],
    ["Found", new Date(NOW.getTime() - 3 * 3_600_000)],
    ["Found", new Date(2026, 10, 13, 9)],
    ["Found", new Date(2026, 10, 10, 9)],
    ["Found", new Date(2026, 10, 2, 9)],
    ["Found", new Date(2025, 11, 30, 9)],
    ["Deadline", new Date(2026, 10, 15, 17)],
  ];
  return (
    <dl className="gx-formats">
      {samples.map(([kind, date], index) => (
        <div key={index}>
          <dt>{kind}</dt>
          <dd>
            <time dateTime={date.toISOString()}>{formatDate(date, NOW)}</time>
          </dd>
        </div>
      ))}
      <div>
        <dt>Count</dt>
        <dd className="ui-num">{formatNumber(25_000)}</dd>
      </div>
    </dl>
  );
}

function Shortcuts() {
  const rows: [string, string[]][] = [
    ["Move in a list", ["J", "K"]],
    ["Open", ["↵"]],
    ["Shortlist · Dismiss", ["S", "D"]],
    ["Undo", ["⌘Z"]],
    ["Search", ["⌘K"]],
    ["Add job", ["N"]],
    ["Go to Jobs", ["G", "J"]],
    ["Shortcuts", ["?"]],
  ];
  return (
    <dl className="gx-keys">
      {rows.map(([label, keys]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>
            {keys.map((key) => (
              <Kbd key={key}>{key}</Kbd>
            ))}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/* ---------------------------------------------------------------- gallery */

function Section({
  id,
  title,
  note,
  children,
}: {
  id: string;
  title: string;
  note?: string;
  children: ReactNode;
}) {
  return (
    <section className="gx-section" aria-labelledby={`gx-${id}`}>
      <header>
        <h2 id={`gx-${id}`}>{title}</h2>
        {note && <p>{note}</p>}
      </header>
      {children}
    </section>
  );
}

function GalleryBody() {
  const [theme, setMode] = useState<ThemeMode>(readTheme);
  // Applied before the state changes, so children read the new tokens.
  const setTheme = (mode: ThemeMode) => {
    applyTheme(mode);
    setMode(mode);
  };
  return (
    <div className="gx">
      <div className="gx-page">
        <header className="gx-head">
          <BrandMark size={28} />
          <div className="gx-head-text">
            <h1>Openings design system</h1>
            <p>The primitives of src/ui in both themes. Synthetic data.</p>
          </div>
          <Segmented
            label="Theme"
            value={theme}
            onChange={setTheme}
            options={[
              { value: "system", label: "System", icon: Monitor },
              { value: "light", label: "Light", icon: Sun },
              { value: "dark", label: "Dark", icon: Moon },
            ]}
          />
        </header>

        <Section
          id="color"
          title="Colour"
          note="Neutral grey, one blue accent, three meanings."
        >
          <Swatches theme={theme} />
        </Section>

        <Section
          id="type"
          title="Type, space, elevation"
          note="Inter, three weights, tabular numbers."
        >
          <div className="gx-grid gx-grid-2">
            <div className="gx-cell">
              <TypeScale />
            </div>
            <div className="gx-cell">
              <Scales />
            </div>
          </div>
        </Section>

        <Section
          id="components"
          title="Components"
          note="Quiet at rest, explicit on intent."
        >
          <div className="gx-grid gx-grid-3">
            <Cell title="Buttons" note="one filled per view">
              <Buttons />
            </Cell>
            <Cell title="Status and counts" note="a glyph, not a pill">
              <StatusAndCounts />
            </Cell>
            <Cell title="Views and filters" note="segmented, chips, toggles">
              <ViewsAndFilters />
            </Cell>
            <Cell title="Menu and popover" note="destructive lives here, last">
              <Menus />
            </Cell>
            <Cell title="Toasts" note="past tense, undo, 6 s">
              <Toasts />
            </Cell>
            <Cell title="Dialogs" note="only for the irreversible">
              <Dialogs />
            </Cell>
            <Cell title="Form fields" note="validate on blur, say how to fix">
              <Fields />
            </Cell>
            <Cell title="Table" note="for comparing, not browsing">
              <Providers />
            </Cell>
            <Cell title="Empty state" note="teaches, then offers the action">
              <EmptyState
                icon={Inbox}
                title="No new jobs"
                actions={
                  <>
                    <Button variant="primary" icon={Plus}>
                      Add job
                    </Button>
                    <Button variant="ghost">Add a source</Button>
                  </>
                }
              >
                Jobs from your sources land here. Add a search, or paste a
                posting address.
              </EmptyState>
            </Cell>
            <Cell title="Page header" note="title and one action">
              <div className="gx-framed">
                <PageHeader
                  title="Data Engineer · Orbit"
                  breadcrumb={[{ label: "Applications", href: "#ui" }]}
                  action={<Button size="sm">Record reply</Button>}
                />
              </div>
            </Cell>
            <Cell title="Loading" note="static skeletons">
              <div className="gx-framed">
                <SkeletonRows rows={3} />
              </div>
            </Cell>
            <Cell title="Dates and numbers" note="one format per kind">
              <Formats />
            </Cell>
            <Cell title="Keyboard" note="every frequent action has a key" wide>
              <Shortcuts />
            </Cell>
          </div>
        </Section>
      </div>
    </div>
  );
}

export default function Gallery() {
  return (
    <ToastProvider>
      <GalleryBody />
    </ToastProvider>
  );
}
