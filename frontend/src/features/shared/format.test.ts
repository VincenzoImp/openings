import { describe, expect, it } from "vitest";

import { formatBytes, formatDuration, formatSalary, relativeDays } from "./format";

describe("format", () => {
  it("formats salary ranges compactly", () => {
    expect(formatSalary({ min_amount: 100000, max_amount: 120000, currency: "CHF" })).toBe(
      "CHF 100k - 120k",
    );
    expect(formatSalary({ min_amount: null, max_amount: 90000, currency: null })).toBe("90k");
    expect(formatSalary({ min_amount: null, max_amount: null, currency: "USD" })).toBe("");
  });

  it("describes dates relative to now", () => {
    const now = new Date("2026-09-08T12:00:00");
    expect(relativeDays("2026-09-08", now)).toBe("today");
    expect(relativeDays("2026-09-07", now)).toBe("yesterday");
    expect(relativeDays("2026-09-01", now)).toBe("7d ago");
    expect(relativeDays("2026-06-01", now)).toBe("2026-06-01");
    expect(relativeDays(null, now)).toBe("");
  });

  it("formats durations and sizes", () => {
    expect(formatDuration(1500)).toBe("25m 0s");
    expect(formatDuration(3700)).toBe("1h 1m");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(3 * 1024 * 1024)).toBe("3.0 MB");
  });
});
