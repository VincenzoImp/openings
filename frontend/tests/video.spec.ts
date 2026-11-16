import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { test as base, expect, type Locator, type Page } from "./fixtures";
import { Reel, settled } from "./reel";

// Dashboard footage for a video (the `video` project, never run in CI).
// It records a running demo workspace (`openings demo`) that an agent works on
// at the same time, so the screens show the agent's real writes. The frames
// are the bare dashboard at three times the pixels, so the video's close-ups
// stay sharp; the video draws the cursor, the clicks, the key chips and the
// captions itself, from the track (reel.ts), which gives each scene its focal
// regions.
//
// $OPENINGS_VIDEO_DEVICE is "desktop" (1280×800) or "mobile" (the phone
// layout at 390×844). One phase per run, from $OPENINGS_VIDEO_PHASE, into
// $OPENINGS_REEL_DIR:
// - before: Today, the sources, then Jobs › New, before the agent starts;
// - live: Jobs › New in real time while the agent works, until the file
//   $OPENINGS_VIDEO_STOP exists; $OPENINGS_REEL_DIR/ready marks the start;
// - after: the agent's dismissals with their reason and history, Ready by
//   priority with the salary to state, Mark applied, and Today.
// $OPENINGS_VIDEO_URL is the demo's address and $OPENINGS_VIDEO_SESSION the
// owner's session cookie (name=value) from its sign-in link. A capture script
// outside the repository starts the demo and the agent and runs the phases:
// `npx playwright test --project=video` with these variables set.
const OUT = process.env.OPENINGS_REEL_DIR;
const PHASE = process.env.OPENINGS_VIDEO_PHASE ?? "";
const URL = process.env.OPENINGS_VIDEO_URL ?? "";
const SESSION = process.env.OPENINGS_VIDEO_SESSION ?? "";
const STOP = process.env.OPENINGS_VIDEO_STOP ?? "";
const MOBILE = process.env.OPENINGS_VIDEO_DEVICE === "mobile";
const SIZE = MOBILE
  ? { width: 390, height: 844 }
  : { width: 1280, height: 800 };
const SCALE = 3;

const test = base.extend<{ session: string }>({
  baseURL: async ({}, use) => use(URL),
  session: async ({}, use) => use(SESSION),
  // The demo is the agent's workspace: nothing to restore.
  seededWorkspace: [async ({}, use) => use(), { auto: true }],
});

test.use({
  signedIn: false,
  viewport: SIZE,
  deviceScaleFactor: SCALE,
  isMobile: MOBILE,
  hasTouch: MOBILE,
  locale: "en-GB",
  timezoneId: "Europe/Amsterdam",
  colorScheme: "light",
});

async function open(page: Page, session: string, hash: string) {
  const [name, ...value] = session.split("=");
  await page.context().addCookies([
    {
      name,
      value: value.join("="),
      domain: "127.0.0.1",
      path: "/",
      httpOnly: true,
      sameSite: "Strict",
    },
  ]);
  await page.addInitScript(() => {
    try {
      localStorage.setItem("openings-theme", "light");
      sessionStorage.setItem("openings-demo-banner", "dismissed");
    } catch {}
  });
  // The employer's site opens in a tab the video does not show; nothing
  // leaves the machine.
  await page
    .context()
    .route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) =>
      route.fulfill({ contentType: "text/html", body: "" }),
    );
  await page.goto(hash);
  await settled(page);
}

test("video footage", async ({ page, session }) => {
  test.skip(
    !OUT || !URL || !SESSION,
    "Run through the video capture, which sets the demo and the output.",
  );
  test.setTimeout(45 * 60_000);
  mkdirSync(OUT!, { recursive: true });
  const main = page.locator("#content");
  const nav = (label: string) =>
    MOBILE
      ? page.locator(".ui-bottombar").getByRole("link", { name: label })
      : page.locator(".ui-app-side").getByRole("link", { name: label });
  const list = page.locator(".jobs-list");
  const reel = new Reel(page, OUT!, {
    size: SIZE,
    overlay: false,
    scale: SCALE,
    quality: 96,
  });
  // A missing element fails the run instead of waiting for ever.
  page.setDefaultTimeout(15_000);
  const visible = (target: Locator) => target.isVisible().catch(() => false);
  /**
   * Go to a screen with its navigation link, or by its address where the
   * phone hides the bottom bar (a job's or an application's page).
   */
  const go = async (label: string, hash: string) => {
    if (await visible(nav(label))) await reel.click(nav(label));
    else await page.goto(hash);
    await settled(page);
  };
  /** Focus on `target` if it is there; the phone hides some parts. */
  const focusIf = async (target: Locator) => {
    if (await visible(target)) await reel.focus(target);
  };

  if (PHASE === "before") {
    await open(page, session, "/#today");
    await reel.record();
    await reel.scene("It collects.", main, "today");
    await reel.pause(900);
    const greeting = main.getByText(/new jobs/).first();
    if (await visible(greeting)) await reel.move(greeting);
    await focusIf(
      main
        .getByText(/ready to apply/)
        .first()
        .locator(".."),
    );
    await reel.pause(1600);
    if (MOBILE) {
      await reel.click(
        page.locator(".ui-bottombar").getByRole("button", { name: "More" }),
      );
      await reel.pause(400);
      await reel.click(page.getByRole("menuitem", { name: "Sources" }));
    } else await reel.click(nav("Sources"));
    await settled(page);
    await reel.scene("Your searches and watched companies.", main, "sources");
    await reel.pause(700);
    await reel.move(page.getByText("Backend roles, Amsterdam"));
    await reel.focus(page.getByText("Backend roles, Amsterdam").locator(".."));
    await reel.pause(1300);
    await reel.move(page.getByText("Voltline Grid Analytics careers"));
    await reel.focus(
      page.getByText("Voltline Grid Analytics careers").locator(".."),
    );
    await reel.pause(1300);
    await reel.click(nav("Jobs"));
    await settled(page);
    await expect(list).toBeVisible();
    await reel.scene("Fresh jobs, no duplicates.", main, "new");
    await reel.pause(800);
    const duplicate = list.getByRole("button", {
      name: /Senior Backend Engineer - Grid Data/,
    });
    if (!MOBILE) {
      await reel.move(list, { x: 220, y: 60 });
      await reel.press("j", "j");
      await reel.pause(600);
      await reel.press("j", "j");
      await reel.pause(600);
    }
    await reel.move(duplicate);
    await reel.focus(duplicate);
    await reel.pause(1400);
    await reel.click(duplicate);
    await settled(page);
    await focusIf(main.getByRole("heading").first());
    await reel.pause(1800);
    await reel.stop();
  }

  if (PHASE === "live") {
    await open(page, session, "/#jobs");
    await expect(list).toBeVisible();
    await reel.record();
    await reel.scene("Your agent prepares.", main, "live");
    await reel.move(list, { x: MOBILE ? 200 : 260, y: 40 });
    writeFileSync(join(OUT!, "ready"), "");
    await reel.live(async () => {
      // The lists read the server again on their own (POLL_MS); the agent's
      // work shows up as it happens. Once New stops changing for a while,
      // the agent is preparing: watch Applications instead.
      let moved = false;
      let last = "";
      let still = Date.now();
      while (!existsSync(STOP)) {
        await page.waitForTimeout(1000);
        if (moved) continue;
        const tab = await page
          .getByRole("tab", { name: /^New/ })
          .textContent({ timeout: 2000 })
          .catch(() => last);
        if (tab !== last) [last, still] = [tab ?? "", Date.now()];
        if (Date.now() - still > 90_000) {
          moved = true;
          await nav("Applications").click();
          await settled(page);
        }
      }
    });
    await reel.stop();
  }

  if (PHASE === "after") {
    await open(page, session, "/#jobs");
    await reel.record();
    // The agent's dismissals, each with its reason and its history.
    await reel.scene("Dismissed, with a reason.", main, "dismissed");
    await reel.pause(500);
    await reel.click(page.getByRole("tab", { name: /^Dismissed/ }));
    await settled(page);
    await reel.pause(700);
    const rows = list.getByRole("button");
    let pick = 0;
    // The first dismissal by the agent: its row names it in the list.
    const count = await rows.count();
    for (let index = 0; index < count; index++)
      if ((await rows.nth(index).textContent())?.includes("Claude Code")) {
        pick = index;
        break;
      }
    await reel.click(rows.nth(pick));
    await settled(page);
    await expect(page.locator(".jobs-dismissal")).toContainText("Claude Code");
    await reel.focus(page.locator(".jobs-dismissal"));
    await reel.pause(2400);
    await reel.click(page.locator(".jobs-history summary"));
    await settled(page);
    await reel.scene(
      "Every agent write is attributed.",
      page.locator(".jobs-history"),
      "history",
    );
    await reel.move(page.locator(".jobs-timeline"));
    await reel.focus(page.locator(".jobs-timeline"));
    await reel.pause(2400);

    // Ready, ranked by priority and deadline, with the salary to state.
    await go("Applications", "/#applications");
    if (!MOBILE) {
      await reel.click(page.getByRole("tab", { name: /^Ready/ }));
      await settled(page);
    }
    await reel.scene("Ranked by priority and deadline.", main, "ready");
    await reel.pause(900);
    const first = main.getByRole("link").first();
    await reel.move(first);
    await reel.focus(first);
    await reel.pause(1600);
    await reel.click(first);
    await settled(page);
    const markApplied = page.getByRole("button", { name: /Mark applied/ });
    await expect(markApplied).toBeVisible();
    await reel.scene(
      "A tailored CV and letter, ready to send.",
      main,
      "application",
    );
    await reel.pause(700);
    await focusIf(main.getByRole("heading", { level: 1 }).first());
    await reel.pause(1300);
    const salary = main.getByText("Salary expectation").first();
    if (await salary.isVisible()) {
      await reel.move(salary);
      await reel.focus(salary.locator(".."));
      await reel.pause(1400);
    }
    // The phone's CV text is a narrow column: the video keeps to the check.
    const cv = main.getByRole("tab", { name: "CV" }).first();
    if (!MOBILE && (await visible(cv))) {
      await reel.click(cv);
      await settled(page);
      await reel.pause(400);
      await focusIf(main.getByRole("tabpanel").first());
      await reel.pause(1200);
    }

    // You apply on the employer's site, then mark it applied.
    const employer = page
      .getByRole("link", { name: /Apply on employer/ })
      .first();
    await reel.scene("You apply, best first.", main, "send");
    await reel.pause(500);
    if (await visible(employer)) {
      await reel.focus(employer);
      const popup = page.context().waitForEvent("page");
      await reel.click(employer);
      await (await popup).close();
      await page.bringToFront();
      // Back in front, the viewer draws the PDFs again.
      await settled(page);
      await reel.pause(500);
    }
    await reel.focus(markApplied);
    if (MOBILE) await reel.click(markApplied);
    else {
      await reel.move(markApplied);
      await reel.press("Shift+Enter", "⇧ ↵");
    }
    await settled(page);
    await reel.pause(1500);

    // Replies, interviews and follow-ups, tracked on Today.
    await go("Today", "/#today");
    await reel.scene("Replies, tracked.", main, "today-after");
    await reel.pause(900);
    const waiting = main.getByText("Waiting for a reply").first();
    await reel.move(waiting);
    await reel.focus(waiting.locator(".."));
    await reel.pause(2200);
    await reel.stop();
  }
});
