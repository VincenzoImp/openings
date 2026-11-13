import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ArrowUpDown,
  Bookmark,
  Building2,
  CircleHelp,
  Clock,
  Copy,
  Ellipsis,
  ExternalLink,
  EyeOff,
  Files,
  Globe,
  House,
  Inbox,
  Layers,
  ListFilter,
  Mail,
  MapPin,
  Monitor,
  Moon,
  NotebookPen,
  Pencil,
  Plus,
  Radar,
  Search,
  Send,
  Settings,
  SlidersHorizontal,
  Sun,
  Trash2,
  TriangleAlert,
  UserRound,
  X,
} from "lucide-react";
import {
  ActionBar,
  AppFrame,
  Avatar,
  BottomBar,
  BrandMark,
  Button,
  Callout,
  Checkbox,
  ConfirmDialog,
  Count,
  DetailBar,
  DetailBody,
  Dialog,
  DialogPreview,
  Dot,
  Drawer,
  EmptyState,
  Field,
  FilterChips,
  formatDate,
  formatDay,
  formatNumber,
  Icon,
  IconButton,
  Input,
  Kbd,
  List,
  ListGroup,
  ListRow,
  ListRows,
  Menu,
  MenuPreview,
  MetaLine,
  MobileTopBar,
  moreMenu,
  NeedsCount,
  PageHeader,
  Popover,
  Properties,
  Prose,
  ReadEdit,
  Segmented,
  Select,
  Sidebar,
  SkeletonRows,
  SplitPane,
  Status,
  STAGES,
  Switch,
  Table,
  Tabs,
  Tag,
  Tags,
  Textarea,
  Toolbar,
  ToneText,
  ToastProvider,
  ToastView,
  useToast,
  applyTheme,
  readTheme,
  type Account,
  type FilterChip,
  type MenuEntry,
  type NavItem,
  type NavSection,
  type Stage,
  type ThemeMode,
} from "..";
import {
  APPLICATIONS,
  JOB_GROUPS,
  NOW,
  PROFILE,
  PROVIDERS,
  type DemoJob,
} from "./data";
import "./gallery.css";

const ALL_JOBS = JOB_GROUPS.flatMap((group) => group.jobs);

/* ------------------------------------------------------------------ shell */

const NAV: NavSection[] = [
  {
    items: [
      { id: "today", label: "Today", icon: House, href: "#ui" },
      {
        id: "jobs",
        label: "Jobs",
        icon: Inbox,
        href: "#ui",
        needs: 11,
        needsLabel: "new jobs",
      },
      {
        id: "applications",
        label: "Applications",
        icon: Send,
        href: "#ui",
        needs: 2,
        needsLabel: "ready applications",
      },
    ],
  },
  {
    label: "You",
    items: [
      { id: "profile", label: "Profile", icon: UserRound, href: "#ui" },
      {
        id: "preferences",
        label: "Preferences",
        icon: SlidersHorizontal,
        href: "#ui",
      },
      { id: "templates", label: "Templates", icon: Files, href: "#ui" },
    ],
  },
  {
    label: "Workspace",
    items: [
      { id: "sources", label: "Sources", icon: Radar, href: "#ui" },
      { id: "settings", label: "Settings", icon: Settings, href: "#ui" },
    ],
  },
];
const [WORK, YOU, WORKSPACE] = NAV;
const BAR_ITEMS: NavItem[] = [...WORK.items, YOU.items[0]];
const MORE_ITEMS: NavItem[] = [...YOU.items.slice(1), ...WORKSPACE.items];

function jobMeta(job: DemoJob) {
  if (job.closes)
    return (
      <ToneText tone="warning">Closes {formatDay(job.closes, NOW)}</ToneText>
    );
  const time = (
    <time dateTime={job.found.toISOString()}>{formatDate(job.found, NOW)}</time>
  );
  if (job.incomplete)
    return (
      <>
        <span className="ui-tone-warning" title="Posting text incomplete">
          <Icon icon={TriangleAlert} size="sm" />
        </span>
        {time}
      </>
    );
  if (job.duplicate)
    return (
      <>
        <span title="Possible duplicate">
          <Icon icon={Layers} size="sm" />
        </span>
        {time}
      </>
    );
  return time;
}

/** The Jobs screen as the new shell would show it, with synthetic data. */
function JobsDemo({
  account,
  preview = true,
}: {
  account: Account;
  preview?: boolean;
}) {
  const toast = useToast();
  const [tab, setTab] = useState("new");
  const [selected, setSelected] = useState("j2");
  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState<string[]>([]);
  const [chips, setChips] = useState<FilterChip[]>([
    { key: "workplace", field: "Workplace", value: "Remote" },
    { key: "location", field: "Location", value: "Zurich" },
  ]);
  const visible = ALL_JOBS.filter((job) => !hidden.includes(job.id));
  const job = visible.find((item) => item.id === selected) ?? visible[0];
  const position = visible.indexOf(job) + 1;

  function dismiss(id: string) {
    const target = ALL_JOBS.find((item) => item.id === id)!;
    setHidden((list) => [...list, id]);
    toast.show({
      message: `Dismissed “${target.title}”`,
      icon: EyeOff,
      action: {
        label: "Undo",
        undo: true,
        run: () => setHidden((list) => list.filter((item) => item !== id)),
      },
    });
  }
  function shortlist(id: string) {
    const target = ALL_JOBS.find((item) => item.id === id)!;
    toast.show({
      message: `Shortlisted “${target.title}”`,
      icon: Bookmark,
      action: { label: "Undo", undo: true, run: () => undefined },
    });
  }
  const step = (delta: number) => {
    const next = visible[position - 1 + delta];
    if (next) setSelected(next.id);
  };

  const filterMenu: MenuEntry[] = [
    {
      heading: "Workplace",
      items: ["Remote", "Hybrid", "On site"].map((value) => ({
        id: `w-${value}`,
        label: value,
        kind: "checkbox" as const,
        checked: chips.some((chip) => chip.value === value),
        onSelect: () =>
          setChips((list) =>
            list.some((chip) => chip.value === value)
              ? list.filter((chip) => chip.value !== value)
              : [...list, { key: `w-${value}`, field: "Workplace", value }],
          ),
      })),
    },
  ];
  const sortMenu: MenuEntry[] = [
    { id: "newest", label: "Newest", kind: "radio", checked: true },
    { id: "deadline", label: "Deadline", kind: "radio", checked: false },
    { id: "company", label: "Company", kind: "radio", checked: false },
  ];
  const rowMenu: MenuEntry[] = [
    { id: "open", label: "Open posting", icon: ExternalLink, kbd: "O" },
    { id: "note", label: "Add note", icon: NotebookPen, kbd: "N" },
    { id: "copy", label: "Copy link", icon: Copy },
    { id: "dup", label: "Mark as duplicate…", icon: Layers },
    "separator",
    { id: "delete", label: "Delete job…", icon: Trash2, danger: true },
  ];

  return (
    <AppFrame
      preview={preview}
      sidebar={
        <Sidebar
          sections={NAV}
          current="jobs"
          account={account}
          onAdd={() =>
            toast.show({ message: "Add job opens here", tone: "success" })
          }
          onSearch={() =>
            toast.show({
              message: "The command palette opens here",
              tone: "success",
            })
          }
        />
      }
      topBar={
        <MobileTopBar
          title="Jobs"
          actions={
            <>
              <IconButton
                icon={Search}
                label="Search"
                size="touch"
                tooltip="none"
              />
              <Menu
                label="Filter"
                items={filterMenu}
                placement="bottom-end"
                trigger={(props) => (
                  <IconButton
                    {...props}
                    icon={ListFilter}
                    label="Filter"
                    size="touch"
                    tooltip="none"
                  />
                )}
              />
              <IconButton
                icon={Plus}
                label="Add job"
                size="touch"
                tooltip="none"
              />
            </>
          }
        />
      }
      bottomBar={
        <BottomBar
          items={BAR_ITEMS}
          current="jobs"
          more={moreMenu(MORE_ITEMS, account)}
        />
      }
    >
      <PageHeader
        title="Jobs"
        action={
          <Button icon={Plus} kbd="N">
            Add job
          </Button>
        }
      />
      <Toolbar
        tools={
          <>
            <SearchBox />
            <Menu
              label="Filter"
              items={filterMenu}
              placement="bottom-end"
              trigger={(props) => (
                <Button {...props} variant="ghost" icon={ListFilter}>
                  Filter
                </Button>
              )}
            />
            <Menu
              label="Sort"
              items={sortMenu}
              placement="bottom-end"
              trigger={(props) => (
                <Button {...props} variant="ghost" icon={ArrowUpDown}>
                  Newest
                </Button>
              )}
            />
          </>
        }
      >
        <Tabs
          label="Jobs"
          idPrefix={preview ? "gx-jobs" : "jobs"}
          value={tab}
          onChange={setTab}
          items={[
            { id: "new", label: "New", count: 11 },
            { id: "shortlist", label: "Shortlist", count: 6 },
            { id: "dismissed", label: "Dismissed", count: 5 },
            { id: "all", label: "All" },
          ]}
        />
      </Toolbar>
      <FilterChips
        chips={chips}
        onRemove={(key) =>
          setChips((list) => list.filter((chip) => chip.key !== key))
        }
        onClear={() => setChips([])}
      />
      <div
        className="gx-split-host"
        id={`${preview ? "gx-jobs" : "jobs"}-panel`}
        role="tabpanel"
        aria-labelledby={`${preview ? "gx-jobs" : "jobs"}-tab-${tab}`}
      >
        <SplitPane
          open={open}
          onClose={() => setOpen(false)}
          label="Job"
          list={
            <List
              label="Jobs to review"
              activeId={job?.id ?? null}
              onActiveChange={(id) => {
                setSelected(id);
                setOpen(true);
              }}
              onOpen={() => setOpen(true)}
              shortcuts={{ s: shortlist, d: dismiss }}
            >
              {JOB_GROUPS.map((group) => {
                const jobs = group.jobs.filter(
                  (item) => !hidden.includes(item.id),
                );
                if (!jobs.length) return null;
                return (
                  <ListGroup
                    key={group.label}
                    label={group.label}
                    count={jobs.length}
                  >
                    {jobs.map((item) => (
                      <ListRow
                        key={item.id}
                        id={item.id}
                        leading={<Dot hidden={!item.unread} />}
                        title={item.title}
                        sub={`${item.company} · ${item.place}`}
                        meta={jobMeta(item)}
                        actions={[
                          {
                            label: "Shortlist",
                            icon: Bookmark,
                            shortcut: "S",
                            onClick: () => shortlist(item.id),
                          },
                          {
                            label: "Dismiss",
                            icon: X,
                            shortcut: "D",
                            onClick: () => dismiss(item.id),
                          },
                        ]}
                      />
                    ))}
                  </ListGroup>
                );
              })}
            </List>
          }
          detail={
            job && (
              <>
                <DetailBar
                  position={position}
                  total={visible.length}
                  onPrevious={() => step(-1)}
                  onNext={() => step(1)}
                  onBack={() => setOpen(false)}
                >
                  <Button variant="ghost" size="sm" icon={ExternalLink}>
                    Posting
                  </Button>
                  <Menu
                    label="Job actions"
                    items={rowMenu}
                    placement="bottom-end"
                    trigger={(props) => (
                      <IconButton
                        {...props}
                        icon={Ellipsis}
                        label="More actions"
                        size="sm"
                      />
                    )}
                  />
                </DetailBar>
                <JobDetail
                  job={job}
                  onShortlist={shortlist}
                  onDismiss={dismiss}
                />
              </>
            )
          }
        />
      </div>
    </AppFrame>
  );
}

function SearchBox() {
  const [value, setValue] = useState("");
  return (
    <span className="gx-search">
      <span className="ui-search">
        <Icon icon={Search} />
        <input
          type="search"
          aria-label="Search jobs"
          placeholder="Search jobs"
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
        <Kbd>/</Kbd>
      </span>
    </span>
  );
}

function JobDetail({
  job,
  onShortlist,
  onDismiss,
}: {
  job: DemoJob;
  onShortlist: (id: string) => void;
  onDismiss: (id: string) => void;
}) {
  return (
    <DetailBody>
      <h2 className="gx-detail-title">{job.title}</h2>
      <div className="gx-stack-8">
        <MetaLine
          items={[
            { icon: Building2, text: job.company, label: "Company" },
            { icon: MapPin, text: `${job.place} · Hybrid`, label: "Place" },
            { icon: Globe, text: "LinkedIn", label: "Source" },
            {
              icon: Clock,
              text: `Found ${formatDate(job.found, NOW)}`,
              label: "Found",
            },
          ]}
        />
      </div>
      <div className="gx-actions">
        <Button
          variant="primary"
          icon={Bookmark}
          kbd="S"
          onClick={() => onShortlist(job.id)}
        >
          Shortlist
        </Button>
        <Button>Start application</Button>
        <Button variant="ghost" kbd="D" onClick={() => onDismiss(job.id)}>
          Dismiss
        </Button>
      </div>
      {job.duplicate && (
        <div className="gx-block">
          <Callout
            icon={Layers}
            title={
              <>
                Possibly the same vacancy as <a href="#ui">Data Engineer</a>
              </>
            }
            actions={
              <>
                <Button size="sm">Merge</Button>
                <Button size="sm" variant="ghost">
                  Not the same
                </Button>
              </>
            }
          >
            Northstar Labs · Greenhouse · 13 Nov. Same company, place and
            posting text.
          </Callout>
        </div>
      )}
      <div className="gx-block-lg">
        <Properties
          items={[
            { label: "Language", value: "Posting in English · German welcome" },
            { label: "Salary", value: "CHF 115–135k" },
            { label: "Deadline", value: "None given" },
            {
              label: "Signals",
              value: (
                <Tags
                  items={["Python", "Airflow", "Energy", "Kafka", "dbt", "SQL"]}
                />
              ),
            },
          ]}
        />
      </div>
      <div className="gx-block-lg">
        <Prose>
          <p>
            {job.company} builds data tools for energy networks. The forecasting
            team turns meter and weather data into hourly load forecasts used by
            three grid operators.
          </p>
          <h3>What you will do</h3>
          <ul>
            <li>
              Own the ingestion pipelines for <mark>smart-meter</mark> and
              weather feeds.
            </li>
            <li>
              Design batch and streaming jobs in <mark>Python</mark> and{" "}
              <mark>Airflow</mark>.
            </li>
            <li>
              Keep the warehouse tables forecasters rely on correct and fast.
            </li>
          </ul>
        </Prose>
      </div>
    </DetailBody>
  );
}

/** Applications on a phone: pill tabs, status glyphs, deadlines. */
function ApplicationsPhone({ account }: { account: Account }) {
  const [tab, setTab] = useState("ready");
  const [selected, setSelected] = useState("a1");
  return (
    <AppFrame
      preview
      sidebar={null}
      topBar={
        <MobileTopBar
          title="Applications"
          actions={
            <>
              <IconButton
                icon={Search}
                label="Search applications"
                size="touch"
                tooltip="none"
              />
              <IconButton
                icon={ListFilter}
                label="Filter applications"
                size="touch"
                tooltip="none"
              />
            </>
          }
        />
      }
      bottomBar={
        <BottomBar
          items={BAR_ITEMS}
          current="applications"
          more={moreMenu(MORE_ITEMS, account)}
        />
      }
    >
      <Toolbar label="Stages">
        <Tabs
          label="Stages"
          idPrefix="gx-apps"
          value={tab}
          onChange={setTab}
          items={[
            { id: "ready", label: "Ready", count: 2 },
            { id: "preparing", label: "Preparing", count: 13 },
            { id: "applied", label: "Applied", count: 16 },
          ]}
        />
      </Toolbar>
      <div
        id="gx-apps-panel"
        role="tabpanel"
        aria-labelledby={`gx-apps-tab-${tab}`}
        className="gx-scroll"
      >
        <List
          label="Applications"
          activeId={selected}
          onActiveChange={setSelected}
        >
          <ListRows>
            {APPLICATIONS.map((item) => (
              <ListRow
                key={item.id}
                id={item.id}
                leading={<Status stage={item.stage}>{""}</Status>}
                title={item.title}
                sub={`${item.company} · ${STAGES[item.stage]}`}
                meta={
                  item.overdue ? (
                    <ToneText tone="danger">Overdue</ToneText>
                  ) : item.deadline ? (
                    <ToneText
                      tone={
                        item.id === "a1"
                          ? "danger"
                          : item.id === "a2"
                            ? "warning"
                            : undefined
                      }
                    >
                      {formatDate(item.deadline, NOW)}
                    </ToneText>
                  ) : (
                    "No deadline"
                  )
                }
              />
            ))}
          </ListRows>
        </List>
      </div>
    </AppFrame>
  );
}

/** A second-level page pushed on a phone: back, content, sticky actions. */
function PushedPhone() {
  const job = ALL_JOBS[1];
  return (
    <AppFrame
      preview
      sidebar={null}
      topBar={
        <MobileTopBar
          title="Jobs"
          back={{ label: "Back to Jobs", onClick: () => undefined }}
          actions={
            <>
              <IconButton
                icon={ExternalLink}
                label="Open posting"
                size="touch"
                tooltip="none"
              />
              <IconButton
                icon={Ellipsis}
                label="More actions"
                size="touch"
                tooltip="none"
              />
            </>
          }
        />
      }
      bottomBar={null}
    >
      <div className="gx-pushed">
        <DetailBody>
          <h2 className="gx-detail-title">{job.title}</h2>
          <div className="gx-stack-8">
            <MetaLine
              items={[
                { icon: Building2, text: job.company },
                { icon: MapPin, text: `${job.place} · Hybrid` },
              ]}
            />
          </div>
          <div className="gx-block">
            <Callout icon={Layers} title="Possibly a duplicate">
              Same text as a Greenhouse posting from 13 Nov.
            </Callout>
          </div>
          <div className="gx-block">
            <Prose>
              <p>
                Northstar Labs builds data tools for energy networks. The
                forecasting team turns meter and weather data into hourly load
                forecasts.
              </p>
              <h3>What you will do</h3>
              <ul>
                <li>
                  Own the ingestion pipelines for smart-meter and weather feeds.
                </li>
                <li>Design batch and streaming jobs in Python.</li>
              </ul>
            </Prose>
          </div>
        </DetailBody>
        <ActionBar>
          <IconButton icon={X} label="Dismiss" tooltip="none" />
          <Button>Start application</Button>
          <Button variant="primary">Shortlist</Button>
        </ActionBar>
      </div>
    </AppFrame>
  );
}

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

/* -------------------------------------------------------------- read/edit */

type ProfileDraft = Pick<
  typeof PROFILE,
  "name" | "location" | "headline" | "email" | "summary"
>;
const FIELDS: (keyof ProfileDraft)[] = [
  "name",
  "location",
  "headline",
  "email",
  "summary",
];

function ProfileBlock({ startEditing = false }: { startEditing?: boolean }) {
  const toast = useToast();
  const [saved, setSaved] = useState<ProfileDraft>(() => ({ ...PROFILE }));
  const [editing, setEditing] = useState(startEditing);
  const [draft, setDraft] = useState<ProfileDraft>(() =>
    startEditing
      ? {
          ...PROFILE,
          email: "alex@example",
          headline: "Data engineer · energy and climate data",
          summary:
            "Six years building data pipelines for utilities and grid operators. I like owning ingestion end to end.",
        }
      : { ...PROFILE },
  );
  const changes = FIELDS.filter((key) => draft[key] !== saved[key]).length;
  const emailError = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(draft.email)
    ? undefined
    : "Add the domain, for example alex@example.com";
  const set =
    (key: keyof ProfileDraft) => (event: { target: { value: string } }) =>
      setDraft((value) => ({ ...value, [key]: event.target.value }));
  return (
    <ReadEdit
      title="Profile"
      editing={editing}
      onEdit={() => {
        setDraft(saved);
        setEditing(true);
      }}
      changes={changes}
      onSave={() => {
        if (emailError) return;
        setSaved(draft);
        setEditing(false);
        toast.show({ message: "Profile saved", tone: "success" });
      }}
      onDiscard={() => {
        setDraft(saved);
        setEditing(false);
      }}
      read={
        <div className="gx-profile">
          <div className="gx-profile-top">
            <Avatar name={saved.name} size={48} />
            <div>
              <p className="gx-profile-name">{saved.name}</p>
              <p className="gx-profile-headline">{saved.headline}</p>
            </div>
          </div>
          <div className="gx-stack-8 gx-block">
            <MetaLine
              items={[
                { icon: MapPin, text: saved.location },
                { icon: Mail, text: saved.email },
                { icon: Globe, text: <a href="#ui">{PROFILE.site}</a> },
              ]}
            />
          </div>
          <p className="gx-profile-summary">{saved.summary}</p>
          <div className="gx-block">
            <Properties
              items={[
                { label: "Target roles", value: PROFILE.roles },
                { label: "Locations", value: PROFILE.locations },
                { label: "Languages", value: PROFILE.languages },
              ]}
            />
          </div>
        </div>
      }
      form={
        <>
          <Field label="Name">
            <Input
              value={draft.name}
              onChange={set("name")}
              autoComplete="name"
            />
          </Field>
          <Field label="Location">
            <Input value={draft.location} onChange={set("location")} />
          </Field>
          <Field label="Headline" className="ui-field-full">
            <Input value={draft.headline} onChange={set("headline")} />
          </Field>
          <Field label="Email" error={emailError} className="ui-field-full">
            <Input value={draft.email} onChange={set("email")} type="email" />
          </Field>
          <Field label="Summary" className="ui-field-full">
            <Textarea
              value={draft.summary}
              onChange={set("summary")}
              rows={3}
            />
          </Field>
        </>
      }
    />
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
    applyTheme(mode, false);
    setMode(mode);
  };
  const toast = useToast();
  const account: Account = useMemo(
    () => ({
      name: "Alex Morgan",
      theme,
      onTheme: setTheme,
      onShortcuts: () =>
        toast.show({
          message: "The shortcut sheet opens here",
          tone: "success",
        }),
      onSignOut: () =>
        toast.show({ message: "Signed out (not really)", tone: "success" }),
    }),
    [theme, toast],
  );
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
          id="shell"
          title="Shell"
          note="Sidebar, page header, toolbar, filters, split list and detail."
        >
          <div className="gx-frame">
            <JobsDemo account={account} />
          </div>
        </Section>

        <Section
          id="mobile"
          title="Mobile"
          note="Bottom bar, pill tabs, pushed detail with actions in thumb reach."
        >
          <div className="gx-phones">
            <div className="gx-phone">
              <ApplicationsPhone account={account} />
            </div>
            <div className="gx-phone">
              <PushedPhone />
            </div>
          </div>
        </Section>

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

        <Section
          id="readedit"
          title="Read first, edit on purpose"
          note="The same profile block in both modes."
        >
          <div className="gx-grid gx-grid-2">
            <ProfileBlock />
            <ProfileBlock startEditing />
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
