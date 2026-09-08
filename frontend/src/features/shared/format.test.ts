import { describe, expect, it } from "vitest";

import { formatBytes, formatDuration, formatSalary, relativeDays } from "./format";

const compact = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 0 });

describe("format", () => {
  it("formats salary ranges compactly in the browser locale", () => {
    expect(formatSalary({ min_amount: 100000, max_amount: 120000, currency: "CHF" })).toBe(
      `CHF ${compact.format(100000)}–${compact.format(120000)}`,
    );
    expect(formatSalary({ min_amount: null, max_amount: 90000, currency: null })).toBe(
      compact.format(90000),
    );
    expect(formatSalary({ min_amount: 80000, max_amount: 80000, currency: "EUR" })).toBe(
      `EUR ${compact.format(80000)}`,
    );
    expect(formatSalary({ min_amount: null, max_amount: null, currency: "USD" })).toBe("");
  });

  it("describes dates relative to now", () => {
    const now = new Date("2026-09-08T12:00:00");
    expect(relativeDays("2026-09-08", now)).toBe("today");
    expect(relativeDays("2026-09-07", now)).toBe("yesterday");
    expect(relativeDays("2026-09-01", now)).toBe("7d ago");
    expect(relativeDays("2026-06-01", now)).not.toContain("ago");
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
