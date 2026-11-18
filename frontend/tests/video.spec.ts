import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { test as base, expect, type Locator, type Page } from "./fixtures";
import { Reel, settled, type Rect } from "./reel";

// Dashboard footage for the walkthrough video (the `video` project, never run
// in CI), from a running demo workspace (`openings demo`) that a real agent
// session has worked on. Each shot is one beat of the video's script, recorded
// on its own (OPENINGS_REEL_DIR/<shot>/: frames, frames.json, track.json) at
// three device pixels per page pixel ($OPENINGS_VIDEO_SCALE), so the phone
// layout and the video's close-ups stay sharp. The video draws
// the cursor, clicks, key chips, captions and underlines itself from each
// shot's track; a shot's anchors are the DOM rectangles it aims at.
//
// $OPENINGS_VIDEO_DEVICE is "desktop" (1440×810) or "mobile" (the phone
// layout at 390×585). $OPENINGS_VIDEO_PHASE is "before" (the agent has not
// started: Jobs › New by hand) or "after" (everything else, on the agent's
// work). $OPENINGS_VIDEO_URL is the demo's address and
// $OPENINGS_VIDEO_SESSION the owner's session cookie (name=value) from its
// sign-in link. A capture script outside the repository starts the demo and
// the agent and runs the phases: `npx playwright test --project=video`.
// The "after" phase also writes checks.json: the Ready order, the PDFs on
// screen, the dismissal that quotes a Preference and the words it shares.
// Its shot Z is one frame for the video's opening card and covers: the
// rank-1 Ready application in a tall desktop window, whatever the device.
const OUT = process.env.OPENINGS_REEL_DIR;
const PHASE = process.env.OPENINGS_VIDEO_PHASE ?? "";
const URL = process.env.OPENINGS_VIDEO_URL ?? "";
const SESSION = process.env.OPENINGS_VIDEO_SESSION ?? "";
const MOBILE = process.env.OPENINGS_VIDEO_DEVICE === "mobile";
const SIZE = MOBILE
  ? { width: 390, height: 585 }
  : { width: 1440, height: 810 };
const SCALE = Number(process.env.OPENINGS_VIDEO_SCALE ?? 3);
/** The window of shot Z: the desktop layout, tall enough for a whole CV. */
const TALL = { width: 1440, height: 1300 };
/** A cursor move, in ms of reel time. */
const MOVE = 600;

const test = base.extend<{ session: string }>({
  baseURL: async ({}, use) => use(URL),
  session: async ({}, use) => use(SESSION),
  // The demo is the agent's workspace: nothing to restore.
  seededWorkspace: [async ({}, use) => use(), { auto: true }],
});

test.use({
  signedIn: false,
  // The capture adds its tooltip style, which the served policy would refuse.
  bypassCSP: true,
  viewport: SIZE,
  deviceScaleFactor: SCALE,
  isMobile: MOBILE,
  hasTouch: MOBILE,
  locale: "en-GB",
  timezoneId: "Europe/Amsterdam",
  colorScheme: "light",
});

// The browser's own tooltip for a `title` (the Apply link, the ★ mark) is
// not part of a screenshot: the capture draws it in the product's tooltip
// style instead.
const TOOLTIPS = `
  .apg-check-links a[title], .pf-star-mark[title] { position: relative; }
  .apg-check-links a[title]:hover::after, .pf-star-mark[title]:hover::after {
    content: attr(title); position: absolute; left: 50%; top: calc(100% + 6px);
    transform: translateX(-50%); z-index: 20; padding: 4px 8px;
    border-radius: var(--r-md); background: var(--primary); color: var(--on-primary);
    font: var(--t-xs); font-weight: var(--w-medium); white-space: pre;
    pointer-events: none; }
`;

async function open(page: Page, session: string) {
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
  await page.addInitScript((css) => {
    try {
      localStorage.setItem("openings-theme", "light");
      sessionStorage.setItem("openings-demo-banner", "dismissed");
    } catch {}
    addEventListener("DOMContentLoaded", () => {
      const style = document.createElement("style");
      style.textContent = css;
      document.head.append(style);
    });
  }, TOOLTIPS);
  // Nothing leaves the machine; Settings › API & agents names the default
  // address, port 8080, as the docs do.
  await page
    .context()
    .route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) =>
      route.fulfill({ contentType: "text/html", body: "" }),
    );
  await page.route("**/api/v1/workspace", async (route) => {
    const response = await route.fetch();
    const info = await response.json();
    await route.fulfill({
      response,
      json: { ...info, origin: "http://127.0.0.1:8080" },
    });
  });
}

/** Words, for comparing a dismissal's reason with a Preference. */
const words = (text: string) =>
  text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .filter(Boolean);

/** The longest run of words `a` and `b` share. */
function shared(a: string, b: string) {
  const x = words(a);
  const y = words(b);
  let best: string[] = [];
  for (let i = 0; i < x.length; i++)
    for (let j = 0; j < y.length; j++) {
      let k = 0;
      while (i + k < x.length && j + k < y.length && x[i + k] === y[j + k]) k++;
      if (k > best.length) best = x.slice(i, i + k);
    }
  return best;
}

/**
 * The client rectangles of the words `phrase` (lowercase words) inside
 * `scope`'s text, found with a DOM range over its text nodes.
 */
async function phraseRects(scope: Locator, phrase: string[]): Promise<Rect[]> {
  return scope.evaluate((root, phrase) => {
    const nodes: Text[] = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) nodes.push(walker.currentNode as Text);
    const text = nodes.map((n) => n.data).join("");
    const pattern = new RegExp(
      phrase
        .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
        .join("[^\\p{L}\\p{N}]+"),
      "iu",
    );
    const found = pattern.exec(text);
    if (!found) return [];
    const at = (offset: number): [Text, number] => {
      for (const node of nodes) {
        if (offset <= node.data.length) return [node, offset];
        offset -= node.data.length;
      }
      const last = nodes[nodes.length - 1];
      return [last, last.data.length];
    };
    const range = document.createRange();
    range.setStart(...at(found.index));
    range.setEnd(...at(found.index + found[0].length));
    return [...range.getClientRects()]
      .filter((r) => r.width > 1)
      .map((r) => ({ x: r.x, y: r.y, width: r.width, height: r.height }));
  }, phrase);
}

const rectOf = async (target: Locator): Promise<Rect> => {
  const box = await target.boundingBox();
  if (!box) throw Error("The anchor is not on screen.");
  return box;
};

test("video footage", async ({ page, session, browser }) => {
  test.skip(
    !OUT || !URL || !SESSION,
    "Run through the video capture, which sets the demo and the output.",
  );
  test.setTimeout(20 * 60_000);
  mkdirSync(OUT!, { recursive: true });
  page.setDefaultTimeout(15_000);
  await open(page, session);
  const main = page.locator("#content");
  const checks: Record<string, unknown> = {
    device: MOBILE ? "mobile" : "desktop",
    pdfViewer: await page.evaluate(() => navigator.pdfViewerEnabled),
  };
  expect(checks.pdfViewer).toBe(true);
  const go = async (hash: string) => {
    await page.goto("/#" + hash);
    await settled(page);
  };
  /** Scroll `target` to `y` page pixels from the top of the viewport. */
  const scrollTo = async (target: Locator, y: number) => {
    await target.scrollIntoViewIfNeeded();
    await target.evaluate((element, y) => {
      const box = element.getBoundingClientRect();
      let parent: HTMLElement | null = element.parentElement;
      while (parent && parent.scrollHeight <= parent.clientHeight + 1)
        parent = parent.parentElement;
      (parent ?? document.scrollingElement!).scrollBy(0, box.top - y);
    }, y);
    await page.waitForTimeout(300);
  };
  /** Record one shot: `run` acts on the reel, then it holds to `ms`. */
  const shot = async (
    id: string,
    ms: number,
    run?: (reel: Reel) => Promise<void>,
  ) => {
    const reel = new Reel(page, join(OUT!, id), {
      size: SIZE,
      scale: SCALE,
      cursor: { x: SIZE.width - 60, y: SIZE.height - 40 },
    });
    await reel.record();
    await reel.scene(id, main, id);
    if (run) await run(reel);
    const left = ms - reel.now() * 1000;
    if (left > 0) await reel.pause(left);
    reel.track.text = await page.locator("body").innerText();
    await reel.stop();
    return reel;
  };
  const write = () =>
    writeFileSync(
      join(OUT!, "checks.json"),
      JSON.stringify(checks, null, 1) + "\n",
    );

  if (PHASE === "before") {
    // L, first half: Today › Waiting for a reply (the agent may close a
    // long-silent application as no reply, as Working with me asks).
    await go("today");
    await scrollTo(
      main.getByRole("heading", { name: /^Waiting for a reply/ }).first(),
      MOBILE ? 20 : 200,
    );
    await shot("L1", 2600);

    // M, first half: Jobs › New by hand.
    await go("jobs");
    const list = page.locator(".jobs-list");
    await expect(list).toBeVisible();
    await shot("M1", 2600, async (reel) => {
      if (MOBILE) return;
      await reel.move(list, { x: 260, y: 60 }, MOVE);
      await reel.pause(100);
      await reel.press("j", "j");
      await reel.pause(150);
      await reel.press("j", "j");
      await reel.pause(150);
      await reel.press("s", "s");
      await reel.pause(350);
      await reel.press("z", "z");
    });
    write();
    return;
  }

  // The Preferences the dismissal is matched against: what you look for
  // first, then what you rule out.
  await go("preferences");
  const section = (title: string) =>
    main
      .getByRole("list", { name: title })
      .getByRole("listitem")
      .allInnerTexts();
  const prefLines = [
    ...(await section("What I'm looking for")),
    ...(await section("What I rule out")),
  ];
  checks.preferences = prefLines;

  // The most recent dismissal by the agent whose reason quotes a Preference
  // (three words or more), for the first Preference one quotes.
  await go("jobs?section=dismissed");
  const rows = page
    .locator(".jobs-list")
    .getByRole("button")
    .filter({ hasText: "Claude Code" });
  const count = await rows.count();
  const reasons: string[] = [];
  for (let index = 0; index < count; index++) {
    // The phone shows a job in place of the list.
    if (MOBILE && index) await go("jobs?section=dismissed");
    await rows.nth(index).click();
    await settled(page);
    reasons.push(await page.locator(".jobs-dismissal").innerText());
  }
  checks.reasons = reasons;
  let pick: {
    index: number;
    reason: string;
    line: string;
    phrase: string[];
  } | null = null;
  for (const line of prefLines) {
    for (let index = 0; index < count && !pick; index++) {
      const run = shared(reasons[index], line);
      if (run.length >= 3)
        pick = { index, reason: reasons[index], line, phrase: run };
    }
    if (pick) break;
  }
  if (!pick) throw Error("No dismissal by the agent quotes a Preference.");
  // The underline marks the run's last words (at most four).
  const marked = pick.phrase.slice(-4);
  checks.dismissal = { ...pick, marked };
  write();

  // B: Preferences › What I'm looking for, the rule underlined.
  await go("preferences");
  const rule = main
    .locator("li")
    .filter({ hasText: pick.line.slice(0, 30) })
    .first();
  await scrollTo(rule, MOBILE ? 120 : 160);
  await shot("B", 5800, async (reel) => {
    reel.anchor("rule", await phraseRects(rule, marked));
  });

  // D: the dismissal, its reason quoting the rule; then hover Restore.
  await go("jobs?section=dismissed");
  await rows.nth(pick.index).click();
  await settled(page);
  const dismissal = page.locator(".jobs-dismissal");
  if (MOBILE)
    await scrollTo(page.getByRole("heading", { level: 1 }).first(), 60);
  await shot("D", 8600, async (reel) => {
    reel.anchor("cu", [await rectOf(dismissal)]);
    reel.anchor("rule", await phraseRects(dismissal, marked));
    // After the close-up: the pointer never moves during one.
    await reel.pause(7200);
    const restore = page
      .getByRole("button", { name: /^Restore/ })
      .filter({ hasText: "Restore" })
      .first();
    if (!MOBILE) await reel.move(restore, undefined, MOVE);
  });

  // E: Ready, ranked best first.
  await go("applications");
  if (MOBILE) {
    const chip = page
      .getByRole("tab", { name: /^Ready/ })
      .or(page.getByRole("link", { name: /^Ready/ }));
    if (
      await chip
        .first()
        .isVisible()
        .catch(() => false)
    ) {
      await chip.first().click();
      await settled(page);
    }
  } else {
    await page.getByRole("tab", { name: /^Ready/ }).click();
    await settled(page);
  }
  const readyRows = main.locator("a").filter({ hasText: /Priority \d/ });
  const ready = await readyRows.evaluateAll((links) =>
    links.map((a) => ({
      text: (a as HTMLElement).innerText.replace(/\s+/g, " ").trim(),
      priority: Number(/Priority (\d+)/.exec(a.textContent ?? "")?.[1]),
      href: a.getAttribute("href"),
    })),
  );
  checks.ready = ready;
  write();
  await shot("E", 3600);

  // A and F: the rank-1 Ready application with its CV and letter as PDFs.
  await page.goto("/" + ready[0].href);
  await settled(page);
  checks.application = {
    href: ready[0].href,
    title: await page.getByRole("heading", { level: 1 }).first().innerText(),
  };
  if (MOBILE) {
    await page.getByRole("tab", { name: "CV" }).first().click();
    await settled(page);
  }
  const pdfs = page
    .locator(".ap-well:has(> .ap-pdf)")
    .filter({ visible: true });
  const cvTop = async () => {
    const well = await rectOf(pdfs.first());
    return {
      x: well.x,
      y: well.y,
      width: well.width,
      height: Math.min(well.height, well.width * 0.62),
    };
  };
  await shot("A", 5800, async (reel) => {
    reel.anchor("pdfs", await Promise.all((await pdfs.all()).map(rectOf)));
  });
  await shot("F", 7200, async (reel) => {
    reel.anchor("pdfs", await Promise.all((await pdfs.all()).map(rectOf)));
    reel.anchor("cu", [await cvTop()]);
    if (MOBILE) {
      await reel.pause(3600);
      await reel.click(page.getByRole("tab", { name: "Letter" }).first());
      await settled(page);
      await reel.snap();
    }
  });

  // Z: the same application in a tall desktop window, one frame: its title
  // and state, and its CV and letter whole.
  const tall = await browser.newContext({
    viewport: TALL,
    deviceScaleFactor: SCALE,
    bypassCSP: true,
    locale: "en-GB",
    timezoneId: "Europe/Amsterdam",
    colorScheme: "light",
  });
  const sheet = await tall.newPage();
  await open(sheet, session);
  await sheet.goto(URL + "/" + ready[0].href);
  await settled(sheet);
  const still = new Reel(sheet, join(OUT!, "Z"), {
    size: TALL,
    scale: SCALE,
    cursor: { x: TALL.width - 60, y: TALL.height - 40 },
  });
  await still.record();
  const rects = (selector: string) =>
    sheet
      .locator(selector)
      .filter({ visible: true })
      .evaluateAll((elements) =>
        elements.map((element) => {
          const { x, y, width, height } = element.getBoundingClientRect();
          return { x, y, width, height };
        }),
      );
  still.anchor("title", await rects(".apg-head h1"));
  still.anchor("meta", await rects(".apg-meta > li"));
  still.anchor("panes", [
    ...(await rects('.apg-pane[data-pane="cv"]')),
    ...(await rects('.apg-pane[data-pane="letter"]')),
  ]);
  still.anchor("pdfs", await rects(".ap-well:has(> .ap-pdf)"));
  still.track.text = await sheet.locator("body").innerText();
  await still.stop();
  await tall.close();

  // G: Apply on the employer's site (never clicked here), then Mark applied.
  if (MOBILE) {
    await page.getByRole("tab", { name: "Check" }).first().click();
    await settled(page);
  }
  const apply = page
    .getByRole("link", { name: /Apply on the employer/ })
    .first();
  const markApplied = page
    .getByRole("button", { name: /^Mark applied/ })
    .first();
  await shot("G", 5400, async (reel) => {
    if (!MOBILE) {
      await reel.pause(100);
      await reel.move(apply, undefined, MOVE);
      await reel.pause(900);
      await reel.click(markApplied, undefined, MOVE);
    } else {
      await reel.pause(1500);
      await reel.click(markApplied, undefined, MOVE);
    }
    await expect(page.getByText(/^Marked applied/)).toBeVisible();
    await reel.snap();
    reel.anchor("toast", [
      await rectOf(page.getByText(/^Marked applied/).first()),
    ]);
  });

  // H: Profile › Experience: approve a highlight, then the ★.
  await go("profile");
  const approve = main.getByRole("button", { name: /^Approve/ }).first();
  if (MOBILE) await scrollTo(approve, 230);
  else
    await scrollTo(
      main.getByRole("heading", { name: /^Experience/ }).first(),
      120,
    );
  await shot("H", 6400, async (reel) => {
    await reel.pause(600);
    await reel.click(approve, undefined, MOVE);
    await page.waitForTimeout(400);
    await reel.snap();
    if (!MOBILE) {
      await reel.pause(900);
      const star = main
        .locator("li")
        .filter({ hasText: /p95 latency/ })
        .locator(".pf-star-mark")
        .first();
      await reel.move(star, undefined, MOVE);
    }
  });

  // I: Preferences › Writing rules.
  await go("preferences");
  await scrollTo(
    main.getByRole("region", { name: "Writing rules" }),
    MOBILE ? 16 : 40,
  );
  await shot("I", 4200);

  // J: Templates › Main CV › Preview.
  await go("templates");
  if (MOBILE) {
    await main.getByText("Main CV", { exact: true }).first().click();
    await settled(page);
  }
  await shot("J", 3000);

  // K: Sources and their counts.
  await go("sources");
  await shot("K", 3200);

  // L, second half: the interview brief.
  await go("applications?section=all");
  await main
    .getByText(/Freightwise/)
    .first()
    .click();
  await settled(page);
  const brief = main.getByText(/^Interview brief/).first();
  await expect(brief).toBeVisible();
  if (MOBILE)
    await scrollTo(main.getByText("History", { exact: true }).first(), 10);
  await shot("L2", 3800, async (reel) => {
    reel.anchor("brief", [await rectOf(brief)]);
  });

  // M, second half: Settings › API & agents.
  await go("settings?section=agents");
  await shot("M2", 3000);
  write();
});
