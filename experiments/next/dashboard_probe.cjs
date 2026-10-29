// Practical walkthrough of the synthetic design preview, not production tests.
const { chromium } = require("playwright");
const fs = require("fs");
(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
    });
    page.setDefaultTimeout(5000);
    const errors = [],
      checks = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    const base = process.env.PREVIEW_URL || "http://127.0.0.1:18773";
    const check = (name, ok) => {
      if (!ok) throw Error(name);
      checks.push(name);
    };
    const state = () =>
      page.evaluate(() =>
        JSON.parse(localStorage.getItem("openings-design-preview-v1")),
      );
    await page.goto(base);
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    for (const route of [
      "overview",
      "inbox",
      "applications",
      "companies",
      "career",
      "templates",
      "settings",
    ]) {
      await page.goto(base + "/#" + route);
      await page.waitForTimeout(25);
      check(
        "desktop_navigation_" + route,
        (await page.locator("h1").count()) === 1,
      );
    }
    await page.goto(base + "/#inbox");
    await page.getByRole("textbox", { name: "Search jobs" }).fill("Cedar");
    check("inbox_search", (await page.locator(".jobrow").count()) === 1);
    await page.getByRole("textbox", { name: "Search jobs" }).fill("");
    async function add() {
      await page.getByRole("button", { name: "Add job", exact: true }).click();
      await page
        .locator("#overlay [name=url]")
        .fill("https://example.test/jobs/review");
      await page.locator("#overlay [name=title]").fill("Review Engineer");
      await page.locator("#overlay [name=company]").fill("Example Review Co");
      await page
        .locator("#overlay [name=posting]")
        .fill("Build Python APIs and improve service reliability.");
      await page
        .getByRole("button", { name: "Add to inbox", exact: true })
        .click();
    }
    await add();
    let s = await state();
    const id = s.jobs.find(
      (j) => j.url === "https://example.test/jobs/review",
    ).id;
    check("manual_ingestion", s.jobs.filter((j) => j.id === id).length === 1);
    await add();
    s = await state();
    check(
      "duplicate_url_preserves_identity",
      s.jobs.filter((j) => j.url === "https://example.test/jobs/review")
        .length === 1,
    );
    await page.getByRole("button", { name: "Notes", exact: true }).click();
    await page
      .locator("#overlay [name=note]")
      .fill("Ask about service ownership.");
    await page.getByRole("button", { name: "Save note", exact: true }).click();
    check(
      "note_saved",
      (await state()).jobs.find((j) => j.id === id).note ===
        "Ask about service ownership.",
    );
    await page.getByRole("button", { name: "Dismiss", exact: true }).click();
    check(
      "dismiss_preserves_job",
      (await state()).jobs.find((j) => j.id === id).triage === "dismissed",
    );
    await page.getByRole("button", { name: "Restore to inbox" }).click();
    check(
      "restore_job",
      (await state()).jobs.find((j) => j.id === id).triage === "inbox",
    );
    await page
      .getByRole("button", { name: "Create application", exact: true })
      .click();
    check(
      "new_application_has_no_invented_pdf",
      (await page.locator("iframe").count()) === 0,
    );
    check(
      "new_application_is_draft",
      (await page.getByLabel("Application stage").inputValue()) === "draft",
    );
    await page.getByLabel("Application stage").selectOption("applied");
    check(
      "manual_stage_change",
      (await state()).applications.find((a) => a.jobId === id).stage ===
        "applied",
    );
    await page
      .getByRole("button", { name: "Close application", exact: true })
      .click();
    await page.goto(base + "/#applications");
    await page.getByRole("button", { name: "List", exact: true }).click();
    check("application_list", (await page.locator("table").count()) === 1);
    await page.getByRole("button", { name: "Board", exact: true }).click();
    check("application_kanban", (await page.locator(".kanban").count()) === 1);
    await page.goto(base + "/#career");
    const old = (await state()).jobs.filter((j) => j.outdated).length;
    await page.locator("input[name=email]").fill("edited@example.test");
    await page
      .getByRole("button", { name: "Save profile", exact: true })
      .click();
    check(
      "contact_edit_does_not_invalidate_scores",
      (await state()).jobs.filter((j) => j.outdated).length === old,
    );
    await page
      .locator("textarea[name=preferences]")
      .fill("Remote backend roles in Switzerland; prefer Python.");
    await page
      .getByRole("button", { name: "Save profile", exact: true })
      .click();
    check(
      "relevant_profile_edit_marks_old_scores",
      (await state()).jobs
        .filter((j) => j.score !== null)
        .every((j) => j.outdated),
    );
    await page.goto(base + "/#settings");
    const was = (await state()).settings.scoring;
    await page
      .getByRole("switch", { name: "Enable AI scoring", exact: true })
      .click();
    check("scoring_toggle", (await state()).settings.scoring === !was);
    await page.getByRole("radio", { name: /Remote service/ }).check();
    check("remote_scoring_mode", (await state()).settings.mode === "remote");
    await page.goto(base + "/#inbox");
    await page.locator(".tabs .tab").filter({ hasText: "Saved" }).click();
    await page.getByRole("button", { name: /Review Engineer/ }).click();
    await page.getByRole("button", { name: "Forget", exact: true }).click();
    await page.getByRole("button", { name: "Forget job", exact: true }).click();
    s = await state();
    check(
      "forget_removes_job_and_application",
      !s.jobs.some((j) => j.id === id) &&
        !s.applications.some((a) => a.jobId === id),
    );
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.goto(base + "/#overview");
    await page.screenshot({
      path: "docs/next/preview/overview.png",
      fullPage: true,
    });
    await page.goto(base + "/#applications");
    await page.screenshot({
      path: "docs/next/preview/applications.png",
      fullPage: true,
    });
    await page.goto(base + "/#inbox");
    await page.screenshot({
      path: "docs/next/preview/inbox.png",
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    for (const route of [
      "overview",
      "inbox",
      "applications",
      "companies",
      "career",
      "templates",
      "settings",
    ]) {
      await page.goto(base + "/#" + route);
      await page.waitForTimeout(25);
      check(
        "mobile_no_page_overflow_" + route,
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      );
    }
    await page.goto(base + "/#inbox");
    await page.screenshot({
      path: "docs/next/preview/mobile.png",
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Open navigation", exact: true })
      .click();
    check(
      "mobile_navigation_opens",
      (await page.locator(".sidebar.open").count()) === 1,
    );
    await page.getByRole("link", { name: "Overview", exact: true }).click();
    await page
      .getByRole("button", { name: "Open navigation", exact: true })
      .click();
    await page.getByRole("button", { name: "Toggle color theme" }).click();
    check(
      "theme_toggle",
      (await page.locator("html").getAttribute("data-theme")) === "dark",
    );
    check("no_javascript_errors", errors.length === 0);
    fs.writeFileSync(
      "docs/next/evidence/dashboard-smoke.json",
      JSON.stringify(
        {
          purpose:
            "interactive synthetic design preview, not production frontend verification",
          checks,
          errors,
          passed: checks.length,
          desktop: { width: 1440, height: 1000 },
          mobile: { width: 390, height: 844 },
        },
        null,
        2,
      ) + "\n",
    );
    console.log(JSON.stringify({ passed: checks.length, errors }));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
