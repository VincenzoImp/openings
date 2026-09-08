import { expect, request } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

import { API_TOKEN, PLAIN_URL, TOKEN_URL } from "../playwright.config";

export interface SeedJob {
  title: string;
  company: string;
  location: string;
  job_url: string;
  description: string;
  status?: string;
  labels?: string[];
  note?: string;
}

export interface JobRow {
  job_id: string;
  title: string;
  status: string;
  labels: string[];
}

/** REST helper used by the seed and by tests that need their own fixtures. */
export class Api {
  constructor(readonly ctx: APIRequestContext) {}

  static async plain(): Promise<Api> {
    return new Api(await request.newContext({ baseURL: PLAIN_URL }));
  }

  static async token(): Promise<Api> {
    return new Api(
      await request.newContext({
        baseURL: TOKEN_URL,
        extraHTTPHeaders: { "X-Openings-Token": API_TOKEN },
      }),
    );
  }

  async dispose(): Promise<void> {
    await this.ctx.dispose();
  }

  async addJob(job: SeedJob): Promise<string> {
    const response = await this.ctx.post("/api/jobs", { data: job });
    expect(response.ok(), await response.text()).toBeTruthy();
    const payload = (await response.json()) as { job_ids: string[] };
    return payload.job_ids[0];
  }

  async find(text: string): Promise<JobRow | null> {
    const response = await this.ctx.get("/api/jobs", {
      params: { text, limit: 5, statuses: "new" },
    });
    // Every status, so a job that moved is still found.
    const all = await this.ctx.get(
      `/api/jobs?text=${encodeURIComponent(text)}&limit=5&${[
        "new",
        "shortlisted",
        "applied",
        "interviewing",
        "offer",
        "rejected",
        "withdrawn",
        "blacklisted",
      ]
        .map((status) => `statuses=${status}`)
        .join("&")}`,
    );
    expect(response.ok()).toBeTruthy();
    const payload = (await all.json()) as { items: JobRow[] };
    return payload.items.find((item) => item.title === text) ?? payload.items[0] ?? null;
  }

  async job(
    jobId: string,
  ): Promise<JobRow & { notes: unknown[]; attachments: unknown[]; events: unknown[] }> {
    const response = await this.ctx.get(`/api/jobs/${jobId}`);
    expect(response.ok()).toBeTruthy();
    return (await response.json()) as JobRow & {
      notes: unknown[];
      attachments: unknown[];
      events: unknown[];
    };
  }

  async setStatus(jobIds: string[], status: string, note?: string): Promise<void> {
    const response = await this.ctx.post("/api/jobs/status", {
      data: { job_ids: jobIds, status, note: note ?? null },
    });
    expect(response.ok()).toBeTruthy();
  }

  async blacklist(jobIds: string[]): Promise<void> {
    const response = await this.ctx.post("/api/blacklist", { data: { job_ids: jobIds } });
    expect(response.ok()).toBeTruthy();
  }

  async addNote(jobId: string, kind: "note" | "qa", body: string, title?: string): Promise<void> {
    const response = await this.ctx.post(`/api/jobs/${jobId}/notes`, {
      data: { kind, body, title: title ?? null },
    });
    expect(response.ok()).toBeTruthy();
  }

  async upload(jobId: string, name: string, text: string, kind = "cv"): Promise<void> {
    const response = await this.ctx.post(`/api/jobs/${jobId}/attachments`, {
      multipart: {
        file: { name, mimeType: "text/plain", buffer: Buffer.from(text, "utf-8") },
        kind,
      },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
  }

  async delete(jobIds: string[]): Promise<void> {
    if (jobIds.length === 0) {
      return;
    }
    await this.ctx.post("/api/jobs/delete", { data: { job_ids: jobIds } });
  }
}

let counter = 0;

/** A posting URL that never collides between tests or projects. */
export function uniqueUrl(): string {
  counter += 1;
  return `https://e2e.example.com/jobs/${Date.now()}-${process.pid}-${counter}`;
}
