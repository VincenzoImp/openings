import { test, expect } from "./fixtures";
import { call, go, ownerSession } from "./session";

// The browser tests' isolation (fixtures.ts): each worker has its own server
// and database, and each test starts from the seeded workspace. One test
// changes the seeded Profile and creates a job; the others, in parallel or
// after it in the same worker, still read the seed. Run with several workers
// and `--repeat-each` to see them interleave.
const SEEDED_NAME = "Alex Morgan";

test.beforeEach(async ({ page }) => {
  await page.context().addCookies(ownerSession());
  await go(page, "today");
});

test("a test changes the seeded workspace", async ({ page }) => {
  const profile = await call(page, "/career/profile");
  expect(profile.name).toBe(SEEDED_NAME);
  await call(page, "/career/profile", "PATCH", {
    expected_version: profile.version,
    name: "Changed by one test",
  });
  await call(page, "/jobs", "POST", {
    title: "Isolation probe",
    company: "Example Labs",
    posting: "Written by one test only.",
  });
  expect((await call(page, "/career/profile")).name).toBe(
    "Changed by one test",
  );
});

for (const reader of ["first", "second", "third"])
  test(`the ${reader} reader sees the seed, whatever ran before`, async ({
    page,
  }) => {
    expect((await call(page, "/career/profile")).name).toBe(SEEDED_NAME);
    const probes = await call(page, "/jobs?q=Isolation%20probe");
    expect(probes.total).toBe(0);
  });
