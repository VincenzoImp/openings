import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { test as base, expect, type Page } from "./fixtures";
import { Reel, settled } from "./reel";

// Dashboard footage for a video (the `video` project, never run in CI).
// It records a running demo workspace (`openings demo`) that an agent works on
// at the same time, so the screens show the agent's real writes. The frames
// are the bare dashboard at twice the pixels, for the video's zooms: the
// video draws the cursor, the clicks, the key chips and the captions itself,
// from the track (reel.ts), which gives each scene its focal regions.
//
// One phase per run, from $OPENINGS_VIDEO_PHASE, into $OPENINGS_REEL_DIR:
// - before: Today, then Jobs › New, before the agent starts;
// - live: Jobs › New in real time while the agent works, until the file
//   $OPENINGS_VIDEO_STOP exists; $OPENINGS_REEL_DIR/ready marks the start;
// - after: the agent's dismissals with their reason and history, Ready by
//   priority with the salary to state, Mark applied (⇧⏎), and the replies.
// $OPENINGS_VIDEO_URL is the demo's address and $OPENINGS_VIDEO_SESSION the
// owner's session cookie (name=value) from its sign-in link. A capture script
// outside the repository starts the demo and the agent and runs the phases:
// `npx playwright test --project=video` with these variables set.
const OUT = process.env.OPENINGS_REEL_DIR;
const PHASE = process.env.OPENINGS_VIDEO_PHASE ?? "";
const URL = process.env.OPENINGS_VIDEO_URL ?? "";
const SESSION = process.env.OPENINGS_VIDEO_SESSION ?? "";
const STOP = process.env.OPENINGS_VIDEO_STOP ?? "";
const SIZE = { width: 1280, height: 800 };

const test = base.extend<{ session: string }>({
  baseURL: async ({}, use) => use(URL),
  session: async ({}, use) => use(SESSION),
  // The demo is the agent's workspace: nothing to restore.
  seededWorkspace: [async ({}, use) => use(), { auto: true }],
});

test.use({
  signedIn: false,
  viewport: SIZE,
  deviceScaleFactor: 2,
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
    page.locator(".ui-app-side").getByRole("link", { name: label });
  const list = page.locator(".jobs-list");

  if (PHASE === "before") {
    await open(page, session, "/#today");
    const reel = new Reel(page, OUT!, { overlay: false, scale: 2 });
    await reel.record();
    await reel.scene("It collects.", main.locator("h1").first(), "today");
    await reel.pause(500);
    await reel.move(main.locator("h1").first());
    await reel.focus(main);
    await reel.pause(1500);
    await reel.click(nav("Sources"));
    await settled(page);
    await reel.scene(
      "From your searches and the companies you follow.",
      main,
      "sources",
    );
    await reel.move(page.getByText("Backend roles, Amsterdam"));
    await reel.focus(page.getByText("Backend roles, Amsterdam"));
    await reel.pause(900);
    await reel.move(page.getByText("Voltline Grid Analytics careers"));
    await reel.focus(page.getByText("Voltline Grid Analytics careers"));
    await reel.pause(900);
    await reel.click(nav("Jobs"));
    await settled(page);
    await expect(list).toBeVisible();
    await reel.scene("Fresh jobs, no duplicates.", list, "new");
    await reel.move(list, { x: 220, y: 60 });
    await reel.pause(500);
    await reel.press("j", "j");
    await reel.pause(700);
    await reel.press("j", "j");
    await reel.pause(700);
    const duplicate = list.getByRole("button", {
      name: /Senior Backend Engineer - Grid Data/,
    });
    await reel.click(duplicate);
    await settled(page);
    await reel.focus(page.locator(".jobs-detail, #content").first());
    await reel.pause(1800);
    await reel.stop();
  }

  if (PHASE === "live") {
    await open(page, session, "/#jobs");
    await expect(list).toBeVisible();
    const reel = new Reel(page, OUT!, { overlay: false, scale: 2 });
    await reel.record();
    await reel.scene("Your agent prepares.", list, "live");
    await reel.move(list, { x: 260, y: 40 });
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
          await page.mouse.move(120, 182, { steps: 12 });
          await nav("Applications").click();
          await settled(page);
        }
      }
    });
    await reel.stop();
  }

  if (PHASE === "after") {
    await open(page, session, "/#jobs");
    const reel = new Reel(page, OUT!, { overlay: false, scale: 2 });
    await reel.record();
    // The agent's dismissals, each with its reason and its history.
    await reel.scene("Dismissed, with a reason.", list, "dismissed");
    await reel.click(page.getByRole("tab", { name: /^Dismissed/ }));
    await settled(page);
    const rows = list.getByRole("button");
    const count = await rows.count();
    for (let index = 0; index < count; index++) {
      await rows.nth(index).click();
      await settled(page);
      if (
        (await page.locator(".jobs-dismissal").textContent())?.includes(
          "Claude Code",
        )
      ) {
        await page.mouse.move(400, 300);
        await reel.click(rows.nth(index));
        break;
      }
    }
    await expect(page.locator(".jobs-dismissal")).toContainText("Claude Code");
    await settled(page);
    await reel.focus(page.locator(".jobs-dismissal"));
    await reel.pause(2200);
    const history = page.locator(".jobs-history summary");
    await reel.click(history);
    await settled(page);
    await reel.scene(
      "Every agent write is attributed.",
      page.locator(".jobs-timeline"),
      "history",
    );
    await reel.move(page.locator(".jobs-timeline"));
    await reel.pause(2200);

    // Ready, ranked by priority and deadline, with the salary to state.
    await reel.click(nav("Applications"));
    await settled(page);
    await reel.click(page.getByRole("tab", { name: /^Ready/ }));
    await settled(page);
    await reel.scene(
      "Ranked by priority and deadline.",
      main.getByRole("tabpanel"),
      "ready",
    );
    await reel.move(main.getByRole("tabpanel"), { x: 300, y: 40 });
    await reel.pause(2000);
    await reel.click(main.getByRole("tabpanel").getByRole("link").first());
    await settled(page);
    await expect(
      page.getByRole("button", { name: /Mark applied/ }),
    ).toBeVisible();
    await reel.scene(
      "A tailored CV and letter, ready to send.",
      main.getByRole("heading", { level: 1 }),
      "application",
    );
    await reel.pause(900);
    await reel.move(main.getByText("Salary expectation"));
    await reel.focus(main.getByText("Salary expectation").locator(".."));
    await reel.pause(1400);
    await reel.click(main.getByRole("tab", { name: "CV" }).first());
    await settled(page);
    await reel.pause(1500);

    // You apply on the employer's site, then mark it applied.
    const employer = main.getByRole("link", { name: /Apply on employer/ });
    await reel.scene("You apply, best first.", employer, "send");
    const popup = page.context().waitForEvent("page");
    await reel.click(employer);
    await (await popup).close();
    await page.bringToFront();
    await reel.pause(500);
    await reel.focus(page.getByRole("button", { name: /Mark applied/ }));
    await reel.move(page.getByRole("button", { name: /Mark applied/ }));
    await reel.press("Shift+Enter", "⇧ ↵");
    await settled(page);
    await reel.pause(1500);

    // Replies, interviews and follow-ups, tracked on Today.
    await reel.click(nav("Today"));
    await settled(page);
    await reel.scene("Replies, tracked.", main, "today-after");
    await reel.move(main.locator("h1").first());
    await reel.pause(2500);
    await reel.stop();
  }
});
