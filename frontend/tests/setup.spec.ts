import { test, expect, type Page } from "./fixtures";
import {
  call,
  fitsViewport,
  go,
  isNarrow,
  ownerSession,
  type Cookies,
} from "./session";

// The setup guide (#setup). The browser-test workspace is populated, so the
// first test answers the reads of a first run itself to show a new workspace;
// the second works on the seeded workspace. Each test starts from the seeded workspace (fixtures.ts).
const cookies: Cookies = ownerSession();
const errors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  errors.set(page, []);
  page.on("pageerror", (error) => errors.get(page)!.push(error.message));
  await page.context().addCookies(cookies);
});
test.afterEach(async ({ page }) => {
  expect(errors.get(page)).toEqual([]);
});

const unique = (name: string) =>
  `${name} ${test.info().project.name} ${Date.now()}`;
const toast = (page: Page, text: string) =>
  expect(page.locator(".toast").last()).toContainText(text);
const steps = (page: Page) =>
  page.getByRole("tablist", { name: "Set-up steps" });
const record = (page: Page) => page.getByRole("list", { name: "Your record" });
const part = (page: Page, title: string) =>
  record(page)
    .locator("> li")
    .filter({ has: page.locator(".title", { hasText: title }) });

/** The reads that tell a first run, answered as an empty workspace does. */
async function emptyWorkspace(page: Page) {
  const empty = { items: [], total: 0, limit: 1, offset: 0 };
  const lists = [
    "/jobs?triage=new&limit=1",
    "/applications?limit=1",
    "/career/knowledge?limit=1",
    "/sources?limit=1",
    "/tokens",
    "/jobs?limit=1",
  ];
  await page.route(
    (url) => lists.some((path) => url.href.endsWith("/api/v1" + path)),
    (route) => route.fulfill({ json: empty }),
  );
  await page.route(
    (url) => url.pathname === "/api/v1/career/profile",
    async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      const response = await route.fetch();
      const profile = await response.json();
      return route.fulfill({
        response,
        json: { ...profile, name: "", headline: "", location: "", email: "" },
      });
    },
  );
}

test("a new workspace opens on the setup guide, which is skipped, continued and opened again", async ({
  page,
}) => {
  await emptyWorkspace(page);
  await page.goto("/");
  await expect(page).toHaveURL(/#setup$/);
  await expect(
    page.getByRole("heading", { name: "Set up your workspace", level: 1 }),
  ).toBeVisible();
  // It opens on the first step that is not done.
  await expect(
    steps(page).getByRole("tab", { name: /Connect your agent/ }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByRole("button", { name: "Create an agent token" }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "MCP configuration" }),
  ).toBeVisible();
  // The steps move with the arrow keys.
  await steps(page)
    .getByRole("tab", { name: /Connect your agent/ })
    .focus();
  await page.keyboard.press("ArrowRight");
  const recordTab = steps(page).getByRole("tab", { name: /Your record/ });
  await expect(recordTab).toBeFocused();
  await expect(recordTab).toHaveAttribute("aria-selected", "true");
  await expect(part(page, "Profile")).toContainText("Not started");
  await expect(part(page, "First searches")).toContainText("Not started");
  await page.keyboard.press("End");
  await expect(
    page.getByRole("heading", { name: "First applications" }),
  ).toBeVisible();
  await fitsViewport(page);

  // Today offers to continue while the guide is not finished.
  await go(page, "today");
  const banner = page.locator(".banner", {
    hasText: "Your workspace is not set up yet.",
  });
  // Let Today finish its reads first: WebKit can drop a click on a link that
  // a late render replaces.
  await page.waitForLoadState("networkidle");
  await banner.getByRole("link", { name: "Continue setting up" }).click();
  await expect(page).toHaveURL(/#setup$/);
  // Skipping goes to Today, and the guide no longer opens by itself.
  await page.getByRole("button", { name: "Skip for now" }).click();
  await expect(page.locator("h1:visible")).toHaveText("Today");
  await expect(banner).toHaveCount(0);
  await page.goto("/");
  await expect(page.locator("h1:visible")).toHaveText("Today");
  // Settings, Account opens it again.
  await go(page, "settings?section=account");
  await page.getByRole("link", { name: "Open setup guide" }).click();
  await expect(page).toHaveURL(/#setup$/);
  await expect(page.locator("h1:visible")).toHaveText("Set up your workspace");
  // A browser that saw a populated workspace first never opens it. (WebKit
  // reports a read cut short by leaving the page as an error: let it finish.)
  await page.waitForLoadState("networkidle");
  await page.unrouteAll({ behavior: "wait" });
  await page.evaluate(() => localStorage.removeItem("openings-setup"));
  await page.goto("/");
  await expect(page.locator("h1:visible")).toHaveText("Today");
  expect(
    await page.evaluate(() => localStorage.getItem("openings-setup")),
  ).toBe(null);
});

test("the setup guide reads the workspace and fills in the basics", async ({
  page,
}) => {
  await go(page, "setup?step=record");
  const current = await call(page, "/career/profile");
  await expect(part(page, "Profile")).toContainText(current.name);
  await expect(part(page, "Profile")).toContainText("Done");
  await expect(part(page, "Career entries")).toContainText("Done");

  // The Profile basics save the fields shown, with the current version.
  await part(page, "Profile")
    .getByRole("button", { name: "Edit the profile" })
    .click();
  const basics = page.getByRole("form", { name: "Profile basics" });
  await expect(basics.getByLabel("Name")).toHaveValue(current.name);
  // Saved as it is, so the documents of the other tests stay current.
  const sent = page.waitForRequest(
    (request) =>
      request.method() === "PATCH" &&
      request.url().endsWith("/api/v1/career/profile"),
  );
  await basics.getByRole("button", { name: "Save the profile" }).click();
  await toast(page, "Profile saved.");
  await expect(basics).toHaveCount(0);
  expect((await sent).postDataJSON()).toEqual({
    expected_version: current.version,
    name: current.name,
    headline: current.headline,
    location: current.location,
    email: current.email,
  });

  // What you look for, and the no-reply period as it is.
  const wanted = unique("Synthetic platform roles");
  await part(page, "Preferences")
    .getByRole("button", { name: /the preferences$/ })
    .click();
  const looking = page.getByRole("form", {
    name: "Add to What I'm looking for",
  });
  await looking.getByLabel("Statement").fill(wanted);
  await looking.getByRole("button", { name: "Add", exact: true }).click();
  await toast(page, "Added to What I'm looking for.");
  await expect(
    page.getByRole("list", { name: "What I'm looking for" }),
  ).toContainText(wanted);
  const stored = (await call(page, "/preferences")) as {
    sections: { section: string; items: { text: string }[] }[];
  };
  expect(
    stored.sections
      .find((section) => section.section === "looking_for")!
      .items.at(-1),
  ).toEqual({ text: wanted });
  const days = (await call(page, "/applications?limit=1")).no_reply.days;
  const period = page.locator("form", {
    has: page.getByRole("heading", {
      name: "When an application counts as unanswered",
    }),
  });
  await expect(period.getByLabel("No reply after (days)")).toHaveValue(
    String(days),
  );
  await period.getByRole("button", { name: "Save the period" }).click();
  await toast(page, `after ${days} days count as no reply`);
  expect((await call(page, "/applications?limit=1")).no_reply.days).toBe(days);
  await fitsViewport(page);

  // A first search, with the form of Collection.
  const name = unique("Setup search");
  await part(page, "First searches")
    .getByRole("button", { name: "Add a search" })
    .click();
  const editor = page.getByRole("dialog", { name: "Add a source" });
  await editor.getByLabel("Name", { exact: true }).fill(name);
  await editor.getByLabel("Keywords").fill("synthetic engineer");
  await editor.getByLabel("Location", { exact: true }).fill("Zurich");
  await editor.getByLabel("Country").fill("switzerland");
  await editor.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.locator(".ui-toast")).toContainText(`Added “${name}”`);
  await expect(editor).toBeHidden();
  const source = (
    await call(page, "/sources?summary=false&limit=200")
  ).items.find((item: { name: string }) => item.name === name);
  expect(source.config).toMatchObject({ query: "synthetic engineer" });
  await call(
    page,
    `/sources/${source.id}?expected_version=${source.version}`,
    "DELETE",
  );

  // Connecting an agent: a token made here, with the client configuration.
  await steps(page)
    .getByRole("tab", { name: /Connect your agent/ })
    .click();
  const used = (await call(page, "/tokens")).items.some(
    (item: { last_used_at?: string }) => item.last_used_at,
  );
  await expect(
    page.getByRole("status").filter({
      hasText: used ? "Connected." : "Waiting for your agent's first call",
    }),
  ).toBeVisible();
  const tokenName = unique("Setup agent");
  await page.getByRole("button", { name: "Create an agent token" }).click();
  const create = page.getByRole("dialog", { name: "New token" });
  await create.getByLabel("Name", { exact: true }).fill(tokenName);
  await create.getByRole("button", { name: "Create token" }).click();
  await expect(
    page
      .getByRole("dialog", { name: "Copy your token" })
      .getByRole("region", { name: "Token" }),
  ).toHaveText(/^op_/);
  await page.getByRole("button", { name: "Done" }).click();
  await expect(
    page.getByRole("region", { name: "MCP configuration" }),
  ).toContainText("/mcp");
  const token = (await call(page, "/tokens")).items.find(
    (item: { name: string }) => item.name === tokenName,
  );
  expect(token.kind).toBe("agent");
  await call(page, `/tokens/${token.id}`, "DELETE");
  if (isNarrow(page)) await fitsViewport(page);
});
