import { test, expect } from "./fixtures";
import { call, go } from "./session";

// The browser tests' isolation (fixtures.ts): each worker has its own server
// and database, and each test starts from the seeded workspace because the
// automatic fixture resets it first. The harness is the same for every
// project, so one test on one project is enough; the backend's
// test_e2e_server.py proves the reset restores everything.
const SEEDED_NAME = "Alex Morgan";

test("the reset before each test restores the seeded workspace", async ({
  page,
  server,
}) => {
  test.skip(
    test.info().project.name !== "chromium",
    "The harness is the same for every project.",
  );
  await go(page, "today");
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

  // What the fixture does before the next test.
  const reset = await fetch(server.url + "/__e2e__/reset", { method: "POST" });
  expect(reset.status).toBe(204);
  expect((await call(page, "/career/profile")).name).toBe(SEEDED_NAME);
  expect((await call(page, "/jobs?q=Isolation%20probe")).total).toBe(0);
});
