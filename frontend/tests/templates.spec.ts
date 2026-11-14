import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test, expect, type Page } from "./fixtures";
import { call, go, isPhone, ownerSession } from "./session";

// Templates: a list grouped CV / Letter beside the selected template, with
// Preview · Source · Files · Limits. Each test starts from the seeded
// workspace (fixtures.ts).
const ROOT = resolve(import.meta.dirname, "../..");
const errors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  errors.set(page, []);
  page.on("pageerror", (error) => errors.get(page)!.push(error.message));
  await page.context().addCookies(ownerSession());
  await go(page, "today");
});
test.afterEach(async ({ page }) => {
  expect(errors.get(page)).toEqual([]);
});

type Template = {
  id: string;
  name: string;
  kind: string;
  version: number;
  is_default: boolean;
  tex?: string;
  rules?: Record<string, unknown>;
};
const all = async (page: Page): Promise<Template[]> =>
  (await call(page, "/templates?summary=false&limit=200")).items;
const named = async (page: Page, name: string) =>
  (await all(page)).find((template) => template.name === name);
const detail = (page: Page) => page.locator(".ui-split-detail");
const dialog = (page: Page) => page.locator("dialog[open]").last();
const menu = async (page: Page) => {
  await detail(page).getByRole("button", { name: "More actions" }).click();
  return page
    .getByRole("menu", { name: /^Template/ })
    .filter({ visible: true });
};

test("a new workspace starts a working CV in one click", async ({ page }) => {
  for (;;) {
    const [template] = (await call(page, "/templates?limit=1")).items;
    if (!template) break;
    await call(
      page,
      `/templates/${template.id}?expected_version=${template.version}`,
      "DELETE",
    );
  }
  await go(page, "templates");
  await expect(page.getByText("No templates yet.")).toBeVisible();
  await page.getByRole("button", { name: "Start from the example CV" }).click();
  await expect(
    detail(page).getByRole("heading", { name: "Example CV", exact: true }),
  ).toBeVisible();
  await expect(
    detail(page).getByRole("tab", { name: "Source" }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    detail(page).getByRole("region", { name: "LaTeX source" }),
  ).toContainText("\\documentclass[10pt,a4paper]{article}");
  const cv = await named(page, "Example CV");
  expect(cv).toMatchObject({ kind: "cv", is_default: true });
  expect(cv!.tex).toBe(readFileSync(resolve(ROOT, "examples/cv.tex"), "utf8"));

  // The letter example and an uploaded .tex file, from New template.
  const create = async (item: string | RegExp) => {
    await page
      .getByRole("button", { name: "New template" })
      .filter({ visible: true })
      .click();
    await page
      .getByRole("menu", { name: "New template" })
      .filter({ visible: true })
      .getByRole("menuitem", { name: item })
      .click();
  };
  await create("Start from the example letter");
  await expect
    .poll(async () => (await named(page, "Example letter"))?.kind)
    .toBe("letter");
  const chooser = page.waitForEvent("filechooser");
  await create(/Upload a \.tex file/);
  await (
    await chooser
  ).setFiles({
    name: "my-cover-letter.tex",
    mimeType: "text/x-tex",
    buffer: Buffer.from("\\documentclass{letter}\n"),
  });
  await expect
    .poll(async () => (await named(page, "My cover letter"))?.kind)
    .toBe("letter");
  await expect(
    page
      .getByRole("region", { name: "Templates", exact: true })
      .getByRole("heading", {
        name: /^Letter/,
      }),
  ).toBeVisible();
});

test("source, files, limits, default, rename, duplicate and delete", async ({
  page,
}) => {
  const seeded = (await named(page, "Synthetic CV 05"))!;
  await call(page, `/templates/${seeded.id}`, "PATCH", {
    expected_version: seeded.version,
    rules: { engine: "lualatex" },
  });
  await go(page, `templates?template=${seeded.id}`);
  const pane = detail(page);
  await expect(
    pane.getByRole("heading", { name: "Synthetic CV 05", exact: true }),
  ).toBeVisible();

  // Source: read first; Edit source → Cancel asks, Save saves.
  await pane.getByRole("tab", { name: "Source" }).click();
  await pane.getByRole("button", { name: "Edit source" }).click();
  const editor = pane.getByRole("textbox", { name: "LaTeX source" });
  await editor.fill("\\documentclass{article}\n% cancelled");
  await pane.getByRole("button", { name: "Cancel", exact: true }).click();
  await dialog(page).getByRole("button", { name: "Discard" }).click();
  await expect(editor).toHaveCount(0);
  await pane.getByRole("button", { name: "Edit source" }).click();
  await editor.fill("\\documentclass{article}\n% v2");
  await pane.getByRole("button", { name: /^Save/ }).click();
  await expect(
    pane.getByRole("region", { name: "LaTeX source" }),
  ).toContainText("% v2");
  expect((await named(page, "Synthetic CV 05"))!.tex).toBe(
    "\\documentclass{article}\n% v2",
  );

  // Files: upload two, a PDF becomes the preview; remove one with a confirm.
  await pane.getByRole("tab", { name: "Files" }).click();
  await pane.getByLabel("Files to upload").setInputFiles([
    {
      name: "resume.cls",
      mimeType: "text/plain",
      buffer: Buffer.from("% synthetic class"),
    },
    {
      name: "sample.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4\n% synthetic sample\n%%EOF"),
    },
  ]);
  const files = pane
    .getByRole("region", { name: "Files" })
    .getByRole("listitem");
  await expect(files).toHaveCount(2);
  await pane.getByRole("tab", { name: "Preview" }).click();
  await expect(
    pane.locator('iframe[title="Sample of Synthetic CV 05"]'),
  ).toBeVisible();
  await pane.getByRole("tab", { name: /^Files/ }).click();
  const pdf = files.filter({ hasText: "sample.pdf" });
  if (isPhone(page)) {
    await pdf.getByRole("button", { name: "More for sample.pdf" }).click();
    await page
      .getByRole("menu", { name: "File sample.pdf" })
      .getByRole("menuitem", { name: "Remove…" })
      .click();
  } else {
    await pdf.hover();
    await pdf.getByRole("button", { name: "Remove sample.pdf" }).click();
  }
  await dialog(page).getByRole("button", { name: "Remove file" }).click();
  await expect(files).toHaveCount(1);
  await pane.getByRole("tab", { name: "Preview" }).click();
  await expect(pane.getByText("No preview")).toBeVisible();

  // Limits: read first, edited on purpose; other rules are kept.
  await pane.getByRole("tab", { name: "Limits" }).click();
  await expect(pane.getByText("No limit")).toHaveCount(3);
  await pane.getByRole("button", { name: "Edit", exact: true }).click();
  await pane.getByLabel("Pages").fill("2");
  await pane.getByLabel("Bullet length").fill("180");
  await pane.getByRole("button", { name: /^Save/ }).click();
  await expect(pane.getByText("2 pages")).toBeVisible();
  expect((await named(page, "Synthetic CV 05"))!.rules).toEqual({
    engine: "lualatex",
    max_pages: 2,
    max_bullet_chars: 180,
  });

  // Default, then the … menu: rename, download, duplicate, delete.
  await pane.getByRole("button", { name: "Set as default" }).click();
  await expect(pane.getByText("Default CV")).toBeVisible();
  expect((await named(page, "Synthetic CV 05"))!.is_default).toBe(true);
  await (await menu(page)).getByRole("menuitem", { name: "Rename" }).click();
  await dialog(page).getByLabel("Name").fill("Synthetic CV renamed");
  await dialog(page).getByRole("button", { name: "Save" }).click();
  await expect(
    pane.getByRole("heading", { name: "Synthetic CV renamed", exact: true }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await (
    await menu(page)
  )
    .getByRole("menuitem", { name: "Download source" })
    .click();
  expect((await download).suggestedFilename()).toBe("synthetic-cv-renamed.tex");
  await (await menu(page)).getByRole("menuitem", { name: "Duplicate" }).click();
  await expect(
    pane.getByRole("heading", {
      name: "Synthetic CV renamed copy",
      exact: true,
    }),
  ).toBeVisible();
  await expect
    .poll(
      async () => (await named(page, "Synthetic CV renamed copy"))?.is_default,
    )
    .toBe(false);
  await (
    await menu(page)
  )
    .getByRole("menuitem", { name: "Delete permanently…" })
    .click();
  await dialog(page).getByRole("button", { name: "Delete template" }).click();
  await expect
    .poll(() => named(page, "Synthetic CV renamed copy"))
    .toBeUndefined();
});

test("the list and the detail scroll on their own", async ({ page }) => {
  test.skip(isPhone(page), "A phone shows one pane at a time.");
  await go(page, "templates?tab=source");
  const list = page.locator(".ui-split-list");
  const pane = detail(page);
  await expect(pane.locator(".tpl-title")).toBeVisible();
  expect(
    await list.evaluate(
      (element) => element.scrollHeight > element.clientHeight,
    ),
  ).toBe(true);
  await list.evaluate((element) => element.scrollTo({ top: 600 }));
  expect(await pane.evaluate((element) => element.scrollTop)).toBe(0);
  expect(
    await pane.evaluate((element) => element.getBoundingClientRect().top),
  ).toBeGreaterThan(0);
  // One "Default" style: the default of each kind is marked the same way.
  await expect(list.locator(".tpl-default")).toHaveCount(2);
});

test("on a phone the list pushes the detail with its tabs", async ({
  page,
}) => {
  test.skip(!isPhone(page), "The pushed detail is a phone layout.");
  await go(page, "templates");
  const list = page.getByRole("region", { name: "Templates", exact: true });
  await list.getByRole("button", { name: /^Synthetic letter/ }).click();
  const pane = detail(page);
  await expect(
    pane.getByRole("heading", { name: "Synthetic letter", exact: true }),
  ).toBeVisible();
  await expect(pane.getByRole("tab")).toHaveText([
    "Preview",
    "Source",
    "Files",
    "Limits",
  ]);
  await pane.getByRole("tab", { name: "Limits" }).click();
  await expect(pane.getByText("1 page")).toBeVisible();
  await pane.getByRole("button", { name: "Back to templates" }).click();
  await expect(page).toHaveURL(/#templates$/);
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(390);
});
