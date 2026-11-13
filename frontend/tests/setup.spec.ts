import { test, expect, type Page } from "./fixtures";
import {
  call,
  card,
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
    "/jobs?queue=inbox&limit=1",
    "/applications?status=draft&limit=1",
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
  await expect(card(page, "Create a token")).toBeVisible();
  await expect(card(page, "Connect an agent")).toBeVisible();
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
  await banner.getByRole("link", { name: "Continue setting up" }).click();
  await expect(page).toHaveURL(/#setup$/);
  // Skipping goes to Today, and the guide no longer opens by itself.
  await page.getByRole("button", { name: "Skip for now" }).click();
  await expect(page.locator(".main h1")).toHaveText("Today");
  await expect(banner).toHaveCount(0);
  await page.goto("/");
  await expect(page.locator(".main h1")).toHaveText("Today");
  // Settings, Workspace opens it again.
  await go(page, "settings?section=workspace");
  await card(page, "Setup guide")
    .getByRole("link", { name: "Open the setup guide" })
    .click();
  await expect(page).toHaveURL(/#setup$/);
  await expect(page.locator(".main h1")).toHaveText("Set up your workspace");
  // A browser that saw a populated workspace first never opens it. (WebKit
  // reports a read cut short by leaving the page as an error: let it finish.)
  await page.waitForLoadState("networkidle");
  await page.unrouteAll({ behavior: "wait" });
  await page.evaluate(() => localStorage.removeItem("openings-setup"));
  await page.goto("/");
  await expect(page.locator(".main h1")).toHaveText("Today");
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

  // A fact employers ask about, and the no-reply period as it is.
  const label = unique("Synthetic permit");
  await part(page, "Policy")
    .getByRole("button", { name: /the policy$/ })
    .click();
  const facts = page.getByRole("form", {
    name: "Add a fact employers ask about",
  });
  await facts.getByLabel("Fact").fill(label);
  await facts
    .getByLabel("What is true for you")
    .fill("Synthetic work permit until 2030.");
  await facts.getByRole("button", { name: "Add the fact" }).click();
  await toast(page, "Added to Eligibility.");
  await expect(
    page.getByRole("list", { name: "Eligibility facts" }),
  ).toContainText(label);
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
  await toast(page, `after ${days} days can be closed as no reply`);
  expect((await call(page, "/applications?limit=1")).no_reply.days).toBe(days);
  const eligibility = (await call(page, "/policy/eligibility")) as {
    version: number;
    items: { id: string; label: string }[];
  };
  const added = eligibility.items.find((item) => item.label === label)!;
  await call(
    page,
    `/policy/items/${added.id}?expected_version=${eligibility.version}`,
    "DELETE",
  );
  await fitsViewport(page);

  // A first search, with the form of Collection.
  const name = unique("Setup search");
  await part(page, "First searches")
    .getByRole("button", { name: "Add a search" })
    .click();
  const editor = page.locator("section", {
    has: page.getByRole("heading", { name: "New search" }),
  });
  await editor.getByLabel("Name", { exact: true }).fill(name);
  await editor.getByLabel("Keywords").fill("synthetic engineer");
  await editor.getByLabel("Location", { exact: true }).fill("Zurich");
  await editor.getByRole("button", { name: "Save the search" }).click();
  await toast(page, "Search saved.");
  await expect(editor).toHaveCount(0);
  const source = (
    await call(page, "/sources?summary=false&limit=200")
  ).items.find((item: { name: string }) => item.name === name);
  expect(source.enabled).toBe(false);
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
  const create = card(page, "Create a token");
  const tokenName = unique("Setup agent");
  await create.getByLabel("Token name").fill(tokenName);
  await create.getByRole("button", { name: "Create", exact: true }).click();
  await expect(create.locator("pre.secret")).toHaveText(/^op_/);
  await expect(
    card(page, "Connect an agent").getByLabel("MCP configuration"),
  ).toContainText("/mcp");
  const token = (await call(page, "/tokens")).items.find(
    (item: { name: string }) => item.name === tokenName,
  );
  expect(token.kind).toBe("agent");
  await call(page, `/tokens/${token.id}`, "DELETE");
  if (isNarrow(page)) await fitsViewport(page);
});
