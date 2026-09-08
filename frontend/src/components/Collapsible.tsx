import { useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

/** Long content starts folded at `lines` lines with a "Show more" control. */
export function Collapsible({
  children,
  lines = 12,
  className = "",
}: {
  children: ReactNode;
  lines?: number;
  className?: string;
}) {
  const body = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [overflows, setOverflows] = useState(false);
  const maxHeight = `${lines * 1.6}rem`;

  useLayoutEffect(() => {
    const node = body.current;
    if (!node) {
      return;
    }
    const measure = () => setOverflows(node.scrollHeight > node.clientHeight + 4);
    measure();
    if (typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [children]);

  return (
    <div className={className}>
      <div
        ref={body}
        className={`relative ${open ? "" : "overflow-hidden"}`}
        style={open ? undefined : { maxHeight }}
      >
        {children}
        {!open && overflows ? (
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-surface to-transparent"
          />
        ) : null}
      </div>
      {overflows || open ? (
        <button
          type="button"
          className="mt-1 text-xs font-medium text-accent hover:underline"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Show less" : "Show more"}
        </button>
      ) : null}
    </div>
  );
}
