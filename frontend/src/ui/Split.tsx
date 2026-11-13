import { useEffect, useRef, type ReactNode } from "react";
import { ChevronDown, ChevronLeft, ChevronUp } from "lucide-react";
import { IconButton } from "./Button";
import { cx } from "./cx";
import { formatNumber } from "./format";
import "./split.css";

/**
 * List and detail side by side at full height, each scrolling on its own.
 * Under 1024 px the detail opens over the list as a 640 px drawer, and under
 * 720 px as a pushed full-screen page; `open` says whether it is shown there,
 * and Esc or the back button close it.
 */
export function SplitPane({
  list,
  detail,
  open,
  onClose,
  label = "Details",
}: {
  list: ReactNode;
  detail: ReactNode;
  open: boolean;
  onClose: () => void;
  label?: string;
}) {
  const detailRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (open) detailRef.current?.scrollTo?.({ top: 0 });
  }, [open]);
  return (
    <div className="ui-split" data-open={open || undefined}>
      <div className="ui-split-list">{list}</div>
      <section
        ref={detailRef}
        className="ui-split-detail"
        aria-label={label}
        onKeyDown={(event) => {
          if (event.key === "Escape" && open) {
            event.stopPropagation();
            onClose();
          }
        }}
      >
        {detail}
      </section>
    </div>
  );
}

/**
 * The sticky 44 px bar of a detail: back (narrow screens), previous/next,
 * "2 of 11", then the caller's tools (Posting ↗, the … menu).
 */
export function DetailBar({
  position,
  total,
  onPrevious,
  onNext,
  onBack,
  backLabel = "Back to list",
  children,
}: {
  position?: number;
  total?: number;
  onPrevious?: () => void;
  onNext?: () => void;
  onBack?: () => void;
  backLabel?: string;
  children?: ReactNode;
}) {
  return (
    <div className="ui-detail-bar">
      {onBack && (
        <IconButton
          icon={ChevronLeft}
          label={backLabel}
          className="ui-detail-back"
          tooltip="none"
          onClick={onBack}
        />
      )}
      {onPrevious && (
        <IconButton
          icon={ChevronUp}
          label="Previous"
          shortcut="K"
          size="sm"
          onClick={onPrevious}
          disabled={position === 1}
        />
      )}
      {onNext && (
        <IconButton
          icon={ChevronDown}
          label="Next"
          shortcut="J"
          size="sm"
          onClick={onNext}
          disabled={position != null && position === total}
        />
      )}
      {position != null && total != null && (
        <span className="ui-detail-pos">
          {formatNumber(position)} of {formatNumber(total)}
        </span>
      )}
      <span className="ui-detail-spacer" />
      {children}
    </div>
  );
}

/**
 * The sticky bottom actions of a pushed page on a phone, inside the safe
 * area: an icon action, then secondary, then primary, each 44 px high.
 */
export function ActionBar({ children }: { children: ReactNode }) {
  return <div className="ui-actionbar">{children}</div>;
}

/** The body of a detail: padded, at most 760 px wide. */
export function DetailBody({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cx("ui-detail-body", className)}>{children}</div>;
}
