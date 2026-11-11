// Shared shell and small interactions for the static dashboard prototypes.
// Each page provides <main id="content" data-page="..."> and this script wraps
// it with the navigation, so the information architecture lives in one place.

const NAV = [
  {
    group: "Work",
    items: [
      { id: "today", label: "Today", href: "today.html" },
      {
        id: "applications",
        label: "Applications",
        href: "applications.html",
        count: 6,
      },
      { id: "jobs", label: "Jobs", href: "jobs.html" },
      { id: "activity", label: "Activity", href: "activity.html", count: 2 },
    ],
  },
  {
    group: "Library",
    items: [
      { id: "career", label: "Career", href: "career.html" },
      { id: "policy", label: "Policy", href: "policy.html" },
      { id: "templates", label: "Templates", href: "templates.html" },
    ],
  },
  {
    group: "System",
    items: [
      { id: "collection", label: "Collection", href: "collection.html" },
      { id: "settings", label: "Settings", href: "settings.html" },
    ],
  },
];
// Narrow screens: four destinations and "More", which opens the remaining pages.
const TABS = ["today", "applications", "jobs", "activity"];

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem("openings-prototype-theme", theme);
  } catch {
    // Storage can be unavailable; the theme then lasts for this page only.
  }
}
function initialTheme() {
  const requested = new URLSearchParams(location.search).get("theme");
  if (requested) return requested;
  try {
    const saved = localStorage.getItem("openings-prototype-theme");
    if (saved) return saved;
  } catch {
    // Fall through to the system preference.
  }
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function shell() {
  const content = document.getElementById("content");
  if (!content) return;
  const page = content.dataset.page;
  const flat = NAV.flatMap((group) => group.items);
  const link = (item) =>
    `<a href="${item.href}"${item.id === page ? ' aria-current="page"' : ""}>${item.label}${
      item.count ? `<span class="count num">${item.count}</span>` : ""
    }</a>`;
  const app = document.createElement("div");
  app.className = "app";
  app.innerHTML = `
    <aside class="sidebar">
      <a class="brand" href="index.html">Openings</a>
      <nav class="nav" aria-label="Main">
        ${NAV.map(
          (
            group,
          ) => `<div class="nav-group stack" style="--s4:2px;margin-bottom:var(--s5)">
            <span class="eyebrow">${group.group}</span>${group.items.map(link).join("")}</div>`,
        ).join("")}
      </nav>
      <div class="sidebar-foot caption">
        <span class="actor agent">career-agent</span><br />
        Run in progress: prepare-shortlist
      </div>
    </aside>
    <div class="main">
      <div class="topbar">
        <span class="muted grow">${content.dataset.crumb || ""}</span>
        <button class="btn quiet sm" id="density" type="button">Density</button>
        <button class="btn quiet sm" id="theme" type="button">Theme</button>
      </div>
    </div>
    <nav class="tabbar" aria-label="Main">
      ${flat
        .filter((item) => TABS.includes(item.id))
        .map(link)
        .join("")}
      <button type="button" id="more" aria-expanded="false" aria-controls="more-sheet"${
        TABS.includes(page) ? "" : ' aria-current="page"'
      }>More</button>
    </nav>
    <nav class="more-sheet nav" id="more-sheet" aria-label="More" hidden>
      ${flat
        .filter((item) => !TABS.includes(item.id))
        .map(link)
        .join("")}
    </nav>`;
  content.replaceWith(app);
  app.querySelector(".main").append(content);
  document.getElementById("theme").addEventListener("click", () => {
    setTheme(
      document.documentElement.dataset.theme === "dark" ? "light" : "dark",
    );
  });
  const more = document.getElementById("more");
  more.addEventListener("click", () => {
    const sheet = document.getElementById("more-sheet");
    sheet.hidden = !sheet.hidden;
    more.setAttribute("aria-expanded", String(!sheet.hidden));
  });
  document.getElementById("density").addEventListener("click", () => {
    const root = document.documentElement;
    root.dataset.density = root.dataset.density === "compact" ? "" : "compact";
  });
}

// Tabs: <div class="tabs" role="tablist"> with buttons [role=tab][aria-controls],
// and panels [role=tabpanel] with matching ids.
function tabs() {
  for (const list of document.querySelectorAll('[role="tablist"]')) {
    const all = [...list.querySelectorAll('[role="tab"]')];
    const select = (tab) => {
      for (const other of all) {
        const on = other === tab;
        other.setAttribute("aria-selected", String(on));
        other.tabIndex = on ? 0 : -1;
        const panel = document.getElementById(
          other.getAttribute("aria-controls"),
        );
        if (panel) panel.hidden = !on;
      }
    };
    list.addEventListener("click", (event) => {
      const tab = event.target.closest('[role="tab"]');
      if (tab) select(tab);
    });
    list.addEventListener("keydown", (event) => {
      const index = all.indexOf(document.activeElement);
      const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
      if (index < 0 || !step) return;
      const next = all[(index + step + all.length) % all.length];
      select(next);
      next.focus();
    });
    select(
      all.find((tab) => tab.getAttribute("aria-selected") === "true") || all[0],
    );
  }
}

// Segmented switch that shows one of several panes on narrow screens:
// <div class="segmented" data-switch="group"> with buttons [data-show="pane id"].
function switches() {
  for (const control of document.querySelectorAll("[data-switch]")) {
    const buttons = [...control.querySelectorAll("[data-show]")];
    const show = (button) => {
      for (const other of buttons) {
        const on = other === button;
        other.setAttribute("aria-pressed", String(on));
        document.getElementById(other.dataset.show).dataset.shown = String(on);
      }
    };
    control.addEventListener("click", (event) => {
      const button = event.target.closest("[data-show]");
      if (button) show(button);
    });
    show(buttons[0]);
  }
}

setTheme(initialTheme());
shell();
tabs();
switches();
