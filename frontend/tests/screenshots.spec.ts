import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { test as base, expect, type Page } from "./fixtures";
import { startServer, type Server } from "./server";
import { blockButton, call, go } from "./session";

// Images of every screen for visual review, not a pixel comparison: `npm run
// screenshots` writes them to frontend/screenshots/ (desktop 1440×1000 and
// mobile 390×844, light and dark), and CI uploads them as the `screenshots`
// artifact of a pull request that changes the dashboard. `npm run screenshots
// -- --docs` writes the images the user documentation and the README embed to
// docs/images/ instead. A new screen or a key state (empty, populated, dialog
// open) gets one line in SCREENS.
//
// The images show a curated synthetic workspace (`dashboard_server.py --demo`:
// one fictional person's job search) or a first run (`--empty`), not the
// browser tests' workspace. Each worker seeds its own.
type Workspace = "demo" | "empty";
const ROOT = resolve(import.meta.dirname, "../..");

/** Seed a workspace into a new snapshot; its owner session cookie. */
function seedWorkspace(kind: Workspace) {
  const directory = mkdtempSync(join(tmpdir(), "openings-shots-"));
  const snapshot = join(directory, "snapshot.sqlite");
  const seeded = spawnSync(
    "uv",
    [
      "run",
      "--project",
      ROOT,
      "python",
      join(ROOT, "backend/tests/dashboard_server.py"),
      "--seed",
      snapshot,
      `--${kind}`,
    ],
    { encoding: "utf8", timeout: 120_000 },
  );
  const line = seeded.stdout?.match(/^\{.*\}$/m)?.[0];
  if (!line)
    throw Error(`The ${kind} workspace was not seeded.\n${seeded.stderr}`);
  return { directory, snapshot, session: JSON.parse(line).session as string };
}

/** A seeded workspace served by this worker. */
type Served = { server: Server; session: string; directory: string };

// Each worker starts a workspace's server the first time a test asks for it.
// The tests' own server (fixtures.ts) is never started: the base URL and the
// reset before each test are the chosen workspace's.
const test = base.extend<
  { workspace: Workspace; session: string },
  { served: (kind: Workspace) => Promise<Served> }
>({
  workspace: ["demo", { option: true }],
  served: [
    async ({}, use) => {
      const running = new Map<Workspace, Promise<Served>>();
      await use((kind) => {
        if (!running.has(kind))
          running.set(
            kind,
            (async () => {
              const seeded = seedWorkspace(kind);
              const server = await startServer({ snapshot: seeded.snapshot });
              return { ...seeded, server };
            })(),
          );
        return running.get(kind)!;
      });
      for (const served of running.values()) {
        const { server, directory } = await served;
        await server.stop();
        rmSync(directory, { recursive: true, force: true });
      }
    },
    { scope: "worker", timeout: 300_000 },
  ],
  baseURL: async ({ workspace, served }, use) =>
    use((await served(workspace)).server.url),
  session: async ({ workspace, served }, use) =>
    use((await served(workspace)).session),
  seededWorkspace: [
    async ({ workspace, served }, use) => {
      const { server } = await served(workspace);
      const response = await fetch(server.url + "/__e2e__/reset", {
        method: "POST",
      });
      if (response.status !== 204)
        throw Error(`The workspace was not reset (${response.status}).`);
      await use();
    },
    { auto: true, timeout: 200_000 },
  ],
});

// Each screen signs in to its own workspace (capture), not the tests' one.
test.use({ signedIn: false });

/** The owner session as cookies for the browser. */
const sessionCookies = (session: string) => {
  const [name, ...value] = session.split("=");
  return [
    {
      name,
      value: value.join("="),
      domain: "127.0.0.1",
      path: "/",
      httpOnly: true,
      sameSite: "Strict" as const,
    },
  ];
};
type Screen = {
  name: string;
  /** The hash route, or a function of the seeded workspace that returns it. */
  route: string | ((page: Page) => Promise<string>);
  /** Answer the screen's reads before it opens (a state the seed lacks). */
  prepare?: (page: Page) => Promise<void>;
  /** Make the state to capture once the screen is shown. */
  open?: (page: Page) => Promise<void>;
  /** The workspace it shows: the demo, or a first run. */
  workspace?: Workspace;
  /** The file name under docs/images, for an image the docs embed. */
  docs?: string;
  /** The same for the dark image (the README's hero). */
  docsDark?: string;
  /** The same for the phone image. Docs images show the viewport only. */
  docsMobile?: string;
  signedOut?: boolean;
  /** Prepare the page before the screen is opened (a replaced response). */
  before?: (page: Page) => Promise<void>;
  /** On a phone the state is a full-screen sheet: capture the viewport. */
  sheet?: boolean;
};

// Job sources and Settings (#227). The browser-test server collects nothing,
// so a failing source and a Test answer are given by a route.
const failingSources = async (page: Page) =>
  page.route(
    (url) => url.pathname === "/api/v1/sources",
    async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      const at = new Date(Date.now() - 2 * 3600_000).toISOString();
      body.items = body.items.map(
        (item: Record<string, unknown>, index: number) =>
          index === 0
            ? {
                ...item,
                last_error:
                  "Blocked by the site (HTTP 403). It may allow requests again later.",
                last_outcome: "failed",
                last_run: { id: "run-1", state: "failed", started_at: at },
              }
            : index === 1
              ? {
                  ...item,
                  enabled: false,
                }
              : {
                  ...item,
                  last_run: {
                    id: `run-${index}`,
                    state: "succeeded",
                    started_at: at,
                    finished_at: at,
                    counts: { received: 24, created: 4 },
                  },
                },
      );
      await route.fulfill({ response, json: body });
    },
  );
/** Settings › API & agents names the default address, port 8080. */
const localOrigin = (page: Page) =>
  page.route("**/api/v1/workspace", async (route) => {
    const response = await route.fetch();
    const info = await response.json();
    await route.fulfill({
      response,
      json: { ...info, origin: "http://localhost:8080" },
    });
  });
const SOURCES_AND_SETTINGS: Screen[] = [
  { name: "sources", route: "sources", docs: "sources" },
  { name: "sources-states", route: "sources", prepare: failingSources },
  { name: "sources-empty", route: "sources", workspace: "empty" },
  {
    name: "sources-checks",
    route: "sources",
    open: async (page) => {
      await page.getByText("Recent checks", { exact: true }).click();
      await expect(
        page.getByRole("list", { name: "Recent checks" }),
      ).toBeVisible();
    },
  },
  {
    name: "sources-editor-test",
    route: "sources",
    prepare: (page) =>
      page.route("**/api/v1/sources/preview", (route) =>
        route.fulfill({
          json: {
            kind: "jobspy",
            total: 14,
            preview_limit: 20,
            items: [
              ["Backend Engineer", "Cobalt Telecom", "Zurich"],
              ["Senior Python Developer", "Fernhill Mobility", "Zurich"],
              ["Platform Engineer", "Meridian Insurance Group", "Zurich"],
              ["Backend Engineer, Data", "Kelpie Labs", "Zurich · Hybrid"],
              ["Software Engineer, APIs", "Tessellate Maps", "Zurich"],
              ["Python Backend Engineer", "Freightwise", "Zurich"],
            ].map(([title, company, location]) => ({
              title,
              company,
              location,
            })),
            diagnostics: [
              {
                provider: "indeed",
                message: "Waiting 5 seconds between requests.",
              },
            ],
          },
        }),
      ),
    open: async (page) => {
      await page.getByRole("button", { name: "Add source" }).first().click();
      const editor = page.getByRole("dialog", { name: "Add a source" });
      await editor.getByLabel("Keywords").fill("backend engineer");
      await editor.getByLabel(/^Location/).fill("Zurich");
      await editor.getByLabel("Country").selectOption("switzerland");
      await editor.getByRole("button", { name: "Test" }).click();
      await expect(editor.getByText("14 jobs found")).toBeVisible();
    },
  },
  { name: "settings", route: "settings" },
  { name: "settings-account", route: "settings?section=account" },
  {
    name: "settings-agents",
    route: "settings?section=agents",
    // The address as an installation shows it, not the test server's port.
    prepare: localOrigin,
    docs: "agents",
  },
  {
    name: "settings-token",
    route: "settings?section=agents",
    prepare: localOrigin,
    open: async (page) => {
      await page.getByRole("button", { name: "New token" }).click();
      const dialog = page.getByRole("dialog", { name: "New token" });
      await dialog.getByLabel("Name", { exact: true }).fill("Claude Code");
      await dialog.getByRole("button", { name: "Create token" }).click();
      await expect(
        page.getByRole("dialog", { name: "Copy your token" }),
      ).toBeVisible();
    },
  },
  { name: "settings-data", route: "settings?section=data" },
  {
    name: "settings-restore",
    route: "settings?section=data",
    open: async (page) => {
      await page.getByRole("button", { name: "Restore from backup…" }).click();
      await expect(
        page.getByRole("dialog", { name: "Restore from backup" }),
      ).toBeVisible();
    },
  },
  { name: "settings-advanced", route: "settings?section=advanced" },
];
/** Open the editor of the entry with this title on the Profile. */
const editEntry = (title: string) => async (page: Page) => {
  await blockButton(page, `Edit ${title}`);
  await expect(page.locator("form.pf-entry-form")).toBeVisible();
};

const SAMPLE_CV = `# Jordan Example
Platform engineer
Lisbon · jordan@example.test

## Experience
### Platform engineer — Example Grid
2021 – Present · Lisbon
- Cut deploy time from 40 to 6 minutes.
- Ran the on-call rotation for four teams.

## Education
### BSc Computer Science — Example University
2014 – 2017`;

/** Today with nothing to do: no Ready, attention or waiting rows. */
async function caughtUp(page: Page) {
  await page.route(/\/api\/v1\/applications\?/, async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    return route.fulfill({ response, json: { ...body, items: [], total: 0 } });
  });
}

const first = async (page: Page, path: string) =>
  (await call(page, path)).items[0].id as string;

/** A rebuilt screen has drawn its data: no skeleton is left. */
async function settledScreen(page: Page) {
  await expect(page.locator(".ui-skeleton")).toHaveCount(0);
}

/** The default CV template. */
async function defaultCv(page: Page) {
  const cv = (await call(page, "/templates?kind=cv&limit=200")).items.find(
    (template: { is_default: boolean }) => template.is_default,
  );
  return cv.id as string;
}

const SCREENS: Screen[] = [
  { name: "sign-in", route: "today", signedOut: true },
  { name: "setup", route: "setup", workspace: "empty", docs: "setup" },
  { name: "setup-jobs", route: "setup?step=jobs", workspace: "empty" },
  { name: "setup-cv", route: "setup?step=cv", workspace: "empty" },
  { name: "setup-done", route: "setup?step=done", workspace: "empty" },
  { name: "today", route: "today", docs: "today", docsDark: "today-dark" },
  { name: "today-caught-up", route: "today", prepare: caughtUp },
  { name: "today-empty", route: "today", workspace: "empty" },
  {
    name: "palette",
    route: "today",
    open: async (page) => {
      await page.keyboard.press("/");
      const palette = page.getByRole("dialog", { name: "Search and commands" });
      await palette.getByRole("combobox").fill("backend");
      await expect(
        palette.getByRole("group", { name: "Jobs" }).getByRole("option"),
      ).not.toHaveCount(0);
    },
  },
  {
    name: "shortcuts",
    route: "today",
    open: async (page) => {
      await page.keyboard.press("?");
      await expect(page.locator("dialog[open]")).toBeVisible();
    },
  },
  {
    name: "applications",
    route: "applications",
    docs: "applications",
    open: settledScreen,
  },
  {
    name: "applications-applied",
    route: "applications?stage=applied",
    open: settledScreen,
  },
  {
    name: "applications-stats",
    route: "applications?section=stats",
    open: settledScreen,
  },
  {
    name: "application-shortlisted",
    route: async (page) =>
      `applications/${await first(page, "/applications?stage=shortlisted&needs=documents&limit=1")}`,
    open: settledScreen,
  },
  {
    name: "ready",
    route: async (page) =>
      `applications/${await first(page, "/applications?stage=ready&sort=deadline&limit=1")}`,
    docs: "ready",
    open: settledScreen,
  },
  {
    name: "application-after-mark-applied",
    route: async (page) =>
      `applications/${await first(page, "/applications?stage=ready&sort=deadline&limit=1")}`,
    open: async (page) => {
      await settledScreen(page);
      await page
        .getByRole("button", { name: "Mark applied" })
        .filter({ visible: true })
        .first()
        .click();
      await expect(page.getByText(/^Marked applied/)).toBeVisible();
      await settledScreen(page);
    },
  },
  {
    name: "application-applied",
    route: async (page) =>
      `applications/${await first(page, "/applications?stage=interview&limit=1")}`,
    open: settledScreen,
  },
  {
    name: "application-record-reply",
    route: async (page) =>
      `applications/${await first(page, "/applications?stage=applied&limit=1")}`,
    open: async (page) => {
      await settledScreen(page);
      await page
        .getByRole("button", { name: "Record reply" })
        .filter({ visible: true })
        .first()
        .click();
      await expect(page.locator("dialog[open]")).toBeVisible();
    },
  },
  { name: "jobs", route: "jobs", docs: "jobs", docsMobile: "jobs-mobile" },
  {
    name: "jobs-selected",
    route: async (page) =>
      `jobs?job=${await first(page, "/jobs?signal=likely_duplicate&triage=new&limit=1")}`,
  },
  {
    name: "jobs-bulk",
    route: "jobs",
    open: async (page) => {
      await page.locator(".jobs-list .ui-row-main").first().focus();
      await page.keyboard.press("x");
      await page.keyboard.press("Shift+J");
      await page.keyboard.press("Shift+J");
      await expect(
        page.getByRole("toolbar", { name: "3 selected" }),
      ).toBeVisible();
    },
  },
  {
    name: "jobs-filter",
    route: "jobs",
    open: async (page) => {
      await page
        .getByRole("button", { name: /^Filter/ })
        .filter({ visible: true })
        .first()
        .click();
    },
  },
  {
    name: "jobs-dismissed",
    route: "jobs?section=dismissed&dismissed_by=agent",
  },
  { name: "jobs-all", route: "jobs?section=all" },
  { name: "jobs-empty", route: "jobs?q=no%20job%20has%20this%20title" },
  {
    name: "jobs-add-dialog",
    route: "jobs",
    open: async (page) => {
      await page
        .getByRole("button", { name: "Add job" })
        .filter({ visible: true })
        .first()
        .click();
      await expect(page.locator("dialog[open]")).toBeVisible();
    },
  },
  { name: "profile", route: "profile", docs: "profile" },
  {
    name: "profile-edit-header",
    sheet: true,
    route: "profile",
    open: async (page) => {
      await blockButton(page, "Edit header");
      await page
        .getByLabel("Headline")
        .fill("Backend engineer, payments and APIs");
    },
  },
  {
    name: "profile-edit-entry",
    sheet: true,
    route: "profile",
    open: editEntry("Backend engineer"),
  },
  {
    name: "profile-add-entry",
    sheet: true,
    route: "profile",
    open: async (page) => {
      await page.getByRole("button", { name: "Add experience" }).click();
      await expect(page.locator("form.pf-entry-form")).toBeVisible();
    },
  },
  {
    name: "profile-import",
    route: "profile",
    open: async (page) => {
      await page
        .getByRole("button", { name: "Import CV text" })
        .first()
        .click();
      await page.getByRole("textbox", { name: "CV text" }).fill(SAMPLE_CV);
      await page.getByRole("button", { name: "Preview" }).click();
      await expect(page.getByText("Check what was found")).toBeVisible();
    },
  },
  { name: "profile-empty", route: "profile", workspace: "empty" },
  { name: "preferences", route: "preferences", docs: "preferences" },
  {
    name: "preferences-editing",
    route: "preferences",
    open: async (page) => {
      const rules = page.getByRole("list", { name: "Writing rules" });
      await rules.getByRole("listitem").nth(2).focus();
      await page.keyboard.press("Enter");
      await expect(
        page.getByRole("textbox", { name: "Statement" }),
      ).toBeFocused();
    },
  },
  { name: "preferences-empty", route: "preferences", workspace: "empty" },
  {
    name: "templates",
    route: async (page) => `templates?template=${await defaultCv(page)}`,
    docs: "templates",
  },
  {
    name: "templates-source",
    route: async (page) =>
      `templates?template=${await defaultCv(page)}&tab=source`,
  },
  { name: "templates-empty", route: "templates", workspace: "empty" },
  ...SOURCES_AND_SETTINGS,
];

const DOCS = !!process.env.OPENINGS_SCREENSHOTS_DOCS;
const VIEWPORTS = {
  desktop: { width: 1440, height: 1000 },
  mobile: { width: 390, height: 844 },
};
const THEMES = ["light", "dark"] as const;

async function capture(
  page: Page,
  session: string,
  screen: Screen,
  path: string,
  viewportOnly = false,
) {
  if (!screen.signedOut)
    await page.context().addCookies(sessionCookies(session));
  // Open a page of the app first, so a route can read the workspace.
  await page.goto("/");
  await screen.before?.(page);
  const route =
    typeof screen.route === "string" ? screen.route : await screen.route(page);
  await screen.prepare?.(page);
  if (screen.signedOut)
    await expect(page.locator("input[name=password]")).toBeVisible();
  else await go(page, route);
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".ui-skeleton-rows")).toHaveCount(0);
  await screen.open?.(page);
  // The shell fills the viewport and its content scrolls inside it. For a
  // full-page image the frame grows with the content instead: the sidebar
  // spans the whole height and the phone's bars sit above and below it.
  if (!viewportOnly) await page.addStyleTag({ content: FULL_PAGE });
  const fullPage =
    !viewportOnly && !(screen.sheet && (page.viewportSize()?.width ?? 0) < 720);
  await page.screenshot({ path, fullPage, animations: "disabled" });
}

const FULL_PAGE = `
  .ui-app { height: auto; min-height: 100dvh; }
  .ui-app-grid { min-height: 100dvh; }
  .ui-app-content { overflow: visible; flex: 1 0 auto; }
  .ui-app-side { height: auto; }
`;

for (const [size, viewport] of Object.entries(VIEWPORTS))
  for (const theme of THEMES)
    for (const workspace of ["demo", "empty"] as const)
      test.describe(`${size} ${theme} ${workspace}`, () => {
        test.use({ viewport, workspace });
        // Seeding a workspace takes a while the first time.
        test.setTimeout(200_000);
        test.beforeEach(async ({ page }) => {
          await page.addInitScript((value) => {
            try {
              localStorage.setItem("openings-theme", value);
            } catch {}
          }, theme);
        });
        for (const screen of SCREENS) {
          if ((screen.workspace ?? "demo") !== workspace) continue;
          const docs =
            size !== "desktop"
              ? theme === "light" && screen.docsMobile
              : theme === "light"
                ? screen.docs
                : screen.docsDark;
          if (DOCS && !docs) continue;
          test(screen.name, async ({ page, session }) => {
            const path = DOCS
              ? join(ROOT, "docs/images", `${docs}.png`)
              : join(
                  ROOT,
                  "frontend/screenshots",
                  `${size}-${theme}`,
                  `${screen.name}.png`,
                );
            await capture(page, session, screen, path, DOCS);
          });
        }
        // The design system gallery (ui.html), which the dashboard never serves.
        if (!DOCS && workspace === "demo")
          test("ui-gallery", async ({ page }) => {
            await page.route("**/ui.html", (route) =>
              route.fulfill({
                path: join(ROOT, "frontend/dist/ui.html"),
                contentType: "text/html",
              }),
            );
            await page.goto("/ui.html");
            await page.waitForLoadState("networkidle");
            await page.screenshot({
              path: join(
                ROOT,
                "frontend/screenshots",
                `${size}-${theme}`,
                "ui-gallery.png",
              ),
              fullPage: true,
              animations: "disabled",
            });
          });
      });
