import { test, expect, type Page } from "./fixtures";
import { startServer, type Server } from "./server";
import { call, fitsViewport, go, heading } from "./session";

const PASSWORD = "synthetic-browser-password";

// The first-run guide (#setup): About you, Find jobs, Your CV, Done. Every
// step writes through an existing operation and reaches Today in four steps.
// The browser-test workspace is populated; each test starts from it.

const unique = (name: string) =>
  `${name} ${test.info().project.name} ${Date.now()}`;
const steps = (page: Page) =>
  page.getByRole("navigation", { name: "Setup steps" });
const current = (page: Page) => steps(page).locator("[aria-current=step]");
const next = (page: Page, name = "Continue") =>
  page.locator(".setup-foot").getByRole("button", { name, exact: true });
/** Nothing about tokens or MCP before the last step. */
async function noAgentText(page: Page) {
  await expect(page.locator("#content")).not.toContainText(/token|MCP/i);
}

test("first run: about you, a search and a job, a CV and the example template, then Today", async ({
  page,
}) => {
  await go(page, "setup");
  await expect(current(page)).toContainText("About you");
  await expect(heading(page)).toHaveText("About you");
  await noAgentText(page);

  // The name is the one thing a step cannot skip.
  const name = page.getByLabel("Your name");
  await name.fill("");
  await next(page).click();
  await expect(page.getByText("Add your name to continue.")).toBeVisible();
  await expect(name).toBeFocused();
  await name.fill("Alex Example");
  const roles = unique("Synthetic data engineer");
  await page.getByLabel("Roles you're after").fill(roles);
  await page.getByLabel("Where").fill("Zurich or remote");
  const before = (await call(page, "/preferences")).settings.spoken_languages;
  const french = page.getByRole("button", { name: "French" });
  await french.click();
  await expect(french).toHaveAttribute(
    "aria-pressed",
    String(!before.includes("fr")),
  );
  await fitsViewport(page);
  await next(page).click();
  await expect(page).toHaveURL(/#setup\?step=jobs$/);

  // What step 1 saved: the name, two statements and the languages.
  expect((await call(page, "/career/profile")).name).toBe("Alex Example");
  const stored = await call(page, "/preferences");
  const looking = stored.sections
    .find((item: { section: string }) => item.section === "looking_for")
    .items.map((item: { text: string }) => item.text);
  expect(looking).toContain(`Roles: ${roles}`);
  expect(looking).toContain("Where: Zurich or remote");
  expect(stored.settings.spoken_languages.includes("fr")).toBe(
    !before.includes("fr"),
  );

  // Step 2: the search starts from step 1; "Save and continue" saves it and
  // adds one job by its link.
  await expect(current(page)).toContainText("Find jobs");
  await noAgentText(page);
  await expect(page.getByLabel("Keywords")).toHaveValue(roles);
  await expect(page.getByLabel("Location")).toHaveValue("Zurich or remote");
  await page.getByLabel("Country").selectOption("switzerland");
  const link = `https://jobs.example.test/${Date.now()}`;
  await page.getByLabel(/^Link/).fill(link);
  await next(page, "Save and continue").click();
  await expect(current(page)).toContainText("Your CV");
  const source = (
    await call(page, "/sources?summary=false&limit=200")
  ).items.find(
    (item: { config: { query?: string } }) => item.config.query === roles,
  );
  expect(source.kind).toBe("jobspy");
  expect(source.config).toMatchObject({
    location: "Zurich or remote",
    country: "switzerland",
  });
  expect(
    (await call(page, `/jobs/resolve?url=${encodeURIComponent(link)}`)).items,
  ).toHaveLength(1);

  // Step 3: pasted CV text read into entries, and the example template.
  await noAgentText(page);
  const entries = (await call(page, "/career/entries?limit=1")).total;
  await page
    .getByLabel("CV text")
    .fill(
      "Data Engineer at Example Labs\n2021 to 2024\nBuilt synthetic pipelines for example data.",
    );
  await page.getByRole("button", { name: "Read it" }).click();
  const add = page.getByRole("button", { name: /^Add \d+ entr/ });
  await expect(add).toBeVisible();
  await add.click();
  await expect(
    page.getByText(/^Added \d+ entr.* to your Profile\.$/),
  ).toBeVisible();
  expect((await call(page, "/career/entries?limit=1")).total).toBeGreaterThan(
    entries,
  );
  await page.getByRole("button", { name: "Use the example template" }).click();
  await expect(
    page.getByText("Added the template “Example CV”."),
  ).toBeVisible();
  const template = (await call(page, "/templates?limit=200")).items.find(
    (item: { name: string }) => item.name === "Example CV",
  );
  expect(template.kind).toBe("cv");
  await next(page).click();

  // Step 4: how Openings is used, and the agent as an option, last.
  await expect(current(page)).toContainText("Done");
  await expect(page.locator("#content")).toContainText(
    "Openings has no AI of its own; nothing happens until you ask your agent.",
  );
  await expect(
    page.getByRole("link", { name: "Set it up in Settings" }),
  ).toHaveAttribute("href", "#settings");
  await fitsViewport(page);
  await next(page, "Go to Today").click();
  await expect(page).toHaveURL(/#today$/);
  await expect(heading(page)).toHaveText("Today");
});

test("first run with skipping: Find jobs and Your CV are skipped, Back returns", async ({
  page,
}) => {
  await go(page, "setup?step=about");
  await next(page).click();
  await expect(page).toHaveURL(/#setup\?step=jobs$/);
  await next(page, "Back").click();
  await expect(page).toHaveURL(/#setup\?step=about$/);
  await next(page).click();
  // With nothing filled in there is only Continue; Skip leaves a search unsaved.
  await page.getByLabel("Keywords").fill("");
  await expect(next(page, "Skip")).toHaveCount(0);
  await expect(next(page)).toBeVisible();
  await page.getByLabel("Keywords").fill("synthetic search left unsaved");
  await next(page, "Skip").click();
  await expect(page).toHaveURL(/#setup\?step=cv$/);
  expect(
    (await call(page, "/sources?summary=false&limit=200")).items.some(
      (item: { config: { query?: string } }) =>
        item.config.query === "synthetic search left unsaved",
    ),
  ).toBe(false);
  await next(page, "Skip").click();
  await expect(page).toHaveURL(/#setup\?step=done$/);
  await next(page, "Go to Today").click();
  await expect(heading(page)).toHaveText("Today");
  // An address that names no step opens the first.
  await go(page, "setup?step=record");
  await expect(current(page)).toContainText("About you");
});

test("an empty search offers a careers page, one click away", async ({
  page,
}) => {
  await page.route("**/api/v1/sources/preview", (route) =>
    route.fulfill({
      json: { kind: "jobspy", total: 0, preview_limit: 20, items: [] },
    }),
  );
  await go(page, "setup?step=jobs");
  // A careers page comes first; the search names the sites it asks.
  const careers = page.getByLabel(/^Careers page address/);
  await expect(page.locator("#setup-careers")).toHaveText(
    "Follow a company's careers page",
  );
  await expect(page.locator("#content")).toContainText(
    "Searches LinkedIn; with a country, also Indeed and Glassdoor.",
  );
  await page.getByLabel("Keywords").fill("synthetic nothing");
  await page
    .getByRole("region", { name: "Or search job sites" })
    .getByRole("button", { name: "Test" })
    .click();
  await expect(page.getByText("No jobs found")).toBeVisible();
  await page.getByRole("button", { name: "Follow a careers page" }).click();
  await expect(careers).toBeFocused();
});

test.describe("a new installation", () => {
  test.use({ signedIn: false });

  test("asks for the setup code from the server's log", async ({ page }) => {
    await page.route("**/api/v1/auth/session", (route) =>
      route.fulfill({
        json: { configured: false, setup_code: true, authenticated: false },
      }),
    );
    const sent: unknown[] = [];
    await page.route("**/api/v1/auth/setup", (route) => {
      sent.push(route.request().postDataJSON());
      return route.fulfill({
        status: 403,
        json: {
          error: {
            code: "setup_code",
            status: 403,
            message:
              "Enter the setup code from the server's log (docker compose logs openings).",
          },
        },
      });
    });
    await page.goto("/");
    const code = page.getByLabel("Setup code");
    await expect(code).toBeFocused();
    await expect(page.locator(".auth")).toContainText(
      "docker compose logs openings",
    );
    await code.fill("k7qm-3xpa");
    await page.getByLabel("Choose a password").fill(PASSWORD);
    await page.getByLabel("Confirm password").fill(PASSWORD);
    await page.getByRole("button", { name: "Create workspace" }).click();
    await expect(page.getByRole("alert")).toContainText(
      "Enter the setup code from the server's log",
    );
    expect(sent).toEqual([{ password: PASSWORD, setup_code: "k7qm-3xpa" }]);
  });
});

test.describe("a new workspace", () => {
  // Its own first-run server: only the password is set, nothing else.
  test.use({ signedIn: false });
  let server: Server;
  test.beforeAll(async () => {
    test.setTimeout(120_000);
    server = await startServer({ empty: true, timeout: 110_000 });
  });
  test.afterAll(async () => server?.stop());

  test("a careers page from setup is checked at once, and the guide resumes", async ({
    page,
  }) => {
    const base = server.url;
    await page.goto(base + "/");
    await page.locator("input[name=password]").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.goto(base + "/#setup");
    await expect(current(page)).toContainText("About you");
    await page.getByLabel("Your name").fill("Alex Example");
    await page.getByLabel("Roles you're after").fill("platform engineer");
    await next(page).click();

    // Find jobs: the title filter starts from the roles; the board is detected.
    await expect(page.getByLabel(/^Title must include/)).toHaveValue(
      "platform engineer",
    );
    const board = `synthetic${Date.now()}`;
    await page
      .getByLabel(/^Careers page address/)
      .fill(`https://boards.greenhouse.io/${board}`);
    await expect(page.locator("#content")).toContainText(
      `Detected: Greenhouse · ${board}`,
    );
    await page.getByLabel("Keywords").fill("");
    await next(page, "Save and continue").click();
    await expect(current(page)).toContainText("Your CV");

    // A reload of the guide opens the first step not done: Your CV.
    await page.goto(base + "/#setup");
    await page.reload();
    await expect(current(page)).toContainText("Your CV");

    // The new source is being checked already, not tomorrow.
    const name = board[0].toUpperCase() + board.slice(1);
    await page.goto(base + "/#sources");
    const row = page.locator(".src-row").filter({ hasText: name });
    await expect(row).toContainText("Checking now…", { timeout: 2_000 });
    // The fake provider answers the check with one synthetic job.
    const collected = await fetch(base + "/__e2e__/collect", {
      method: "POST",
    });
    expect(collected.status).toBe(204);
    await page.reload();
    await expect(row).toContainText("1 new");
    await page.goto(base + "/#jobs");
    await expect(page.locator("#content")).toContainText(
      "Synthetic platform engineer",
    );
  });
});
