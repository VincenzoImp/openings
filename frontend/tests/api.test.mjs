import { test } from "node:test";
import assert from "node:assert/strict";

// The browser's window: the client signals sign-in and changes on it.
globalThis.window = new EventTarget();
const { api, call, setCsrf, ApiError } = await import("../src/api/client.ts");

function respond(status, body) {
  const requests = [];
  globalThis.fetch = async (request) => {
    requests.push(request);
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  };
  return requests;
}

test("a write carries the session's CSRF token and returns the data", async () => {
  setCsrf("synthetic-csrf");
  const requests = respond(200, { id: "n_1", body: "Synthetic.", version: 1 });
  const note = await call(
    api.POST("/api/v1/jobs/{job_id}/notes", {
      params: { path: { job_id: "j_1" } },
      body: { body: "Synthetic." },
    }),
  );
  assert.equal(note.id, "n_1");
  assert.equal(requests[0].headers.get("X-CSRF-Token"), "synthetic-csrf");
  assert.equal(new URL(requests[0].url).pathname, "/api/v1/jobs/j_1/notes");
});

test("a failed request throws the backend's error and a 401 asks to sign in", async () => {
  respond(409, {
    error: {
      code: "conflict",
      status: 409,
      message: "This record changed.",
      details: { current_version: 3, id: "j_1" },
    },
  });
  await assert.rejects(
    call(
      api.GET("/api/v1/jobs/{job_id}", { params: { path: { job_id: "j_1" } } }),
    ),
    (error) =>
      error instanceof ApiError &&
      error.code === "conflict" &&
      error.currentVersion === 3,
  );
  let unauthorized = 0;
  window.addEventListener("openings:unauthorized", () => unauthorized++);
  respond(401, {
    error: { code: "unauthorized", status: 401, message: "Sign in." },
  });
  await assert.rejects(call(api.GET("/api/v1/jobs")), { status: 401 });
  respond(401, {
    error: { code: "unauthorized", status: 401, message: "Sign in." },
  });
  await assert.rejects(call(api.GET("/api/v1/auth/session")));
  assert.equal(unauthorized, 1);
});
