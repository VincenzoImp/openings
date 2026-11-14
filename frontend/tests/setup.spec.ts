import { test, expect, type Page } from "./fixtures";
import {
  call,
  fitsViewport,
  go,
  heading,
  ownerSession,
  type Cookies,
} from "./session";

// The first-run guide (#setup): About you, Find jobs, Your CV, Done. Every
// step writes through an existing operation and reaches Today in four steps.
// The browser-test workspace is populated; each test starts from it.
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
