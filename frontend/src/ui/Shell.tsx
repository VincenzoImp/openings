import type { ReactNode } from "react";
import {
  ChevronLeft,
  ChevronsUpDown,
  Ellipsis,
  Keyboard,
  LogOut,
  Plus,
  Search,
} from "lucide-react";
import { Avatar, NeedsCount } from "./Badge";
import { IconButton, Kbd } from "./Button";
import { cx } from "./cx";
import { BrandMark, Icon, type LucideIcon } from "./Icon";
import { Menu, type MenuEntry, type MenuGroup } from "./Menu";
import type { ThemeMode } from "./theme";
import "./shell.css";

export interface NavItem {
  id: string;
  label: string;
  icon: LucideIcon;
  href: string;
  /** A "needs you" count (new jobs, ready applications): the accent pill. */
  needs?: number;
  /** What the count is, for its accessible name: "new jobs". */
  needsLabel?: string;
}
export interface NavSection {
  /** Sentence case; the first group has none. */
  label?: string;
  items: NavItem[];
}

export interface Account {
  name: string;
  theme: ThemeMode;
  onTheme: (mode: ThemeMode) => void;
  onShortcuts?: () => void;
  onSignOut: () => void;
}

/** The Theme choice of the account and More menus. */
function themeGroup(account: Account): MenuGroup {
  const option = (mode: ThemeMode, label: string) => ({
    id: `theme-${mode}`,
    label,
    kind: "radio" as const,
    checked: account.theme === mode,
    onSelect: () => account.onTheme(mode),
  });
  return {
    heading: "Theme",
    items: [
      option("system", "System"),
      option("light", "Light"),
      option("dark", "Dark"),
    ],
  };
}

/** The account menu: Theme, Keyboard shortcuts, Sign out. */
export function accountMenu(account: Account): MenuEntry[] {
  return [
    themeGroup(account),
    "separator",
    ...(account.onShortcuts
      ? [
          {
            id: "shortcuts",
            label: "Keyboard shortcuts",
            icon: Keyboard,
            kbd: "?",
            onSelect: account.onShortcuts,
          },
        ]
      : []),
    {
      id: "sign-out",
      label: "Sign out",
      icon: LogOut,
      onSelect: account.onSignOut,
    },
  ];
}

/**
 * The desktop sidebar (240 px, the subtle background): the brand with the
 * global Add job, the search that opens the command palette (⌘K), the
 * navigation groups with icons and "needs you" counts, and the account row
 * with its menu.
 */
export function Sidebar({
  sections,
  current,
  onAdd,
  onSearch,
  account,
}: {
  sections: NavSection[];
  current: string;
  onAdd: () => void;
  onSearch: () => void;
  account: Account;
}) {
  return (
    <nav className="ui-sidebar" aria-label="Main">
      <div className="ui-sidebar-brand">
        <BrandMark />
        <span className="ui-sidebar-name">Openings</span>
        <IconButton icon={Plus} label="Add job" shortcut="N" onClick={onAdd} />
      </div>
      <button
        type="button"
        className="ui-sidebar-search"
        onClick={onSearch}
        aria-keyshortcuts="Meta+K Control+K /"
      >
        <Icon icon={Search} />
        <span>Search</span>
        <Kbd>⌘K</Kbd>
      </button>
      {sections.map((section, index) => (
        <div
          className="ui-nav-section"
          key={section.label ?? index}
          role="group"
          aria-label={section.label ?? "Work"}
        >
          {section.label && (
            <p className="ui-nav-label" aria-hidden="true">
              {section.label}
            </p>
          )}
          <ul>
            {section.items.map((item) => (
              <li key={item.id}>
                <a
                  className="ui-nav-item"
                  href={item.href}
                  aria-current={item.id === current ? "page" : undefined}
                >
                  <Icon icon={item.icon} />
                  <span className="ui-nav-text">{item.label}</span>
                  {item.needs ? (
                    <NeedsCount
                      value={item.needs}
                      label={item.needsLabel ?? "need you"}
                    />
                  ) : null}
                </a>
              </li>
            ))}
          </ul>
        </div>
      ))}
      <div className="ui-sidebar-foot">
        <Menu
          label="Account"
          placement="top-start"
          items={accountMenu(account)}
          trigger={(props) => (
            <button type="button" className="ui-account" {...props}>
              <Avatar name={account.name} />
              <span className="ui-account-name">{account.name}</span>
              <Icon icon={ChevronsUpDown} size="sm" />
            </button>
          )}
        />
      </div>
    </nav>
  );
}

/**
 * The phone's top bar (52 px): an optional back chevron, the title and up to
 * three icon buttons (Search, Filter, Add).
 */
export function MobileTopBar({
  title,
  back,
  actions,
}: {
  title: string;
  back?: { label: string; href?: string; onClick?: () => void };
  actions?: ReactNode;
}) {
  return (
    <header className="ui-topbar">
      {back &&
        (back.href ? (
          <a
            className="ui-btn ui-icon-btn"
            data-variant="ghost"
            data-size="touch"
            href={back.href}
            aria-label={back.label}
          >
            <Icon icon={ChevronLeft} size="lg" />
          </a>
        ) : (
          <IconButton
            icon={ChevronLeft}
            label={back.label}
            size="touch"
            tooltip="none"
            onClick={back.onClick}
          />
        ))}
      <h1 className={cx("ui-topbar-title", back && "ui-topbar-title-sub")}>
        {title}
      </h1>
      {actions && <div className="ui-topbar-actions">{actions}</div>}
    </header>
  );
}

/**
 * The phone's bottom bar (60 px): four destinations and More, icon above
 * label, with "needs you" counts on the icons.
 */
export function BottomBar({
  items,
  current,
  more,
}: {
  items: NavItem[];
  current: string;
  /** The rest of the navigation, the theme and sign out. */
  more: MenuEntry[];
}) {
  const inMore = !items.some((item) => item.id === current);
  return (
    <nav className="ui-bottombar" aria-label="Main">
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <a
              className="ui-tab-item"
              href={item.href}
              aria-current={item.id === current ? "page" : undefined}
            >
              <span className="ui-tab-icon">
                <Icon icon={item.icon} size="lg" />
                {item.needs ? (
                  <NeedsCount
                    value={item.needs}
                    label={item.needsLabel ?? "need you"}
                  />
                ) : null}
              </span>
              <span>{item.label}</span>
            </a>
          </li>
        ))}
        <li>
          <Menu
            label="More"
            placement="top-end"
            items={more}
            trigger={(props) => (
              <button
                type="button"
                className="ui-tab-item"
                data-current={inMore || undefined}
                {...props}
              >
                <span className="ui-tab-icon">
                  <Icon icon={Ellipsis} size="lg" />
                </span>
                <span>More</span>
              </button>
            )}
          />
        </li>
      </ul>
    </nav>
  );
}

/** The More menu of the bottom bar: the other destinations, Theme, Sign out. */
export function moreMenu(items: NavItem[], account: Account): MenuEntry[] {
  return [
    ...items.map((item) => ({
      id: item.id,
      label: item.label,
      icon: item.icon,
      onSelect: () => {
        window.location.hash = item.href.replace(/^#/, "");
      },
    })),
    "separator",
    themeGroup(account),
    "separator",
    {
      id: "sign-out",
      label: "Sign out",
      icon: LogOut,
      onSelect: account.onSignOut,
    },
  ];
}

/**
 * The application frame. It is the `app` container every primitive's narrow
 * layout queries: at 720 px and up the sidebar sits beside the content; below
 * it the top bar and the bottom bar take over.
 */
export function AppFrame({
  sidebar,
  topBar,
  bottomBar,
  children,
  className,
  preview = false,
}: {
  sidebar: ReactNode;
  topBar?: ReactNode;
  bottomBar: ReactNode;
  children: ReactNode;
  className?: string;
  /** Drawn inside a documentation page: no <main> landmark of its own. */
  preview?: boolean;
}) {
  const Content = preview ? "div" : "main";
  return (
    <div className={cx("ui-app", className)}>
      <div className="ui-app-grid">
        <div className="ui-app-side">{sidebar}</div>
        <div className="ui-app-main">
          {topBar}
          <Content
            className="ui-app-content"
            id={preview ? undefined : "content"}
            tabIndex={preview ? undefined : -1}
          >
            {children}
          </Content>
          <div className="ui-app-bottom">{bottomBar}</div>
        </div>
      </div>
    </div>
  );
}
