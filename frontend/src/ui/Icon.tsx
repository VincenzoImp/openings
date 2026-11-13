import type { LucideIcon } from "lucide-react";
import { cx } from "./cx";
import "./icon.css";

export type { LucideIcon };

const SIZES = { sm: 14, md: 16, lg: 20 } as const;
export type IconSize = keyof typeof SIZES;

/**
 * A Lucide icon at the system's sizes: 16 px in the interface, 14 px in meta
 * lines and 20 px in the mobile bars, always with a 1.75 stroke. Decorative:
 * the control around it carries the accessible name.
 */
export function Icon({
  icon: Glyph,
  size = "md",
  className,
}: {
  icon: LucideIcon;
  size?: IconSize;
  className?: string;
}) {
  return (
    <Glyph
      className={cx("ui-icon", className)}
      size={SIZES[size]}
      strokeWidth={1.75}
      aria-hidden="true"
      focusable="false"
    />
  );
}

/** The stages of an application, each with its own 14 px glyph. */
export const STAGES = {
  shortlisted: "Shortlisted",
  ready: "Ready",
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  closed: "Closed",
} as const;
export type Stage = keyof typeof STAGES;

/**
 * The status glyph of a stage: dashed circle (Shortlisted), ring with a dot
 * (Ready), half pie (Applied), three-quarter pie (Interview), filled check
 * (Offer) and crossed circle (Closed). Colour comes from the stage class.
 */
export function StatusGlyph({ stage }: { stage: Stage }) {
  return (
    <svg
      className="ui-glyph"
      data-stage={stage}
      viewBox="0 0 14 14"
      width="14"
      height="14"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
      focusable="false"
    >
      {stage === "shortlisted" && (
        <circle cx="7" cy="7" r="5.5" strokeDasharray="2.2 2" />
      )}
      {stage === "ready" && (
        <>
          <circle cx="7" cy="7" r="5.5" />
          <circle cx="7" cy="7" r="2" fill="currentColor" stroke="none" />
        </>
      )}
      {stage === "applied" && (
        <>
          <circle cx="7" cy="7" r="5.5" />
          <path
            d="M7 7V3.5A3.5 3.5 0 0 1 7 10.5Z"
            fill="currentColor"
            stroke="none"
          />
        </>
      )}
      {stage === "interview" && (
        <>
          <circle cx="7" cy="7" r="5.5" />
          <path
            d="M7 7V3.5A3.5 3.5 0 1 1 3.5 7Z"
            fill="currentColor"
            stroke="none"
          />
        </>
      )}
      {stage === "offer" && (
        <>
          <circle cx="7" cy="7" r="6.25" fill="currentColor" stroke="none" />
          <path
            className="ui-glyph-check"
            d="M4.4 7.2l1.8 1.7 3.4-3.6"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </>
      )}
      {stage === "closed" && (
        <>
          <circle cx="7" cy="7" r="5.5" />
          <path d="M5 5l4 4M9 5l-4 4" strokeLinecap="round" />
        </>
      )}
    </svg>
  );
}

/** The brand mark: a ring with a notch, on the primary fill. */
export function BrandMark({ size = 24 }: { size?: number }) {
  return (
    <span className="ui-mark" style={{ width: size, height: size }}>
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        aria-hidden="true"
        focusable="false"
      >
        <circle cx="12" cy="12" r="7" />
        <path d="M12 5v4" />
      </svg>
    </span>
  );
}
