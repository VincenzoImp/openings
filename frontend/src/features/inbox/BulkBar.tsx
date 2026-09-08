import { Ban, Check, Star, Tag, Trash2, X } from "lucide-react";

import { Button } from "../../components/Button";

export function BulkBar({
  count,
  onClear,
  onShortlist,
  onApplied,
  onStatus,
  onLabels,
  onBlacklist,
  onDelete,
}: {
  count: number;
  onClear: () => void;
  onShortlist: () => void;
  onApplied: () => void;
  onStatus: () => void;
  onLabels: () => void;
  onBlacklist: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      role="toolbar"
      aria-label="Bulk actions"
      className="sticky top-0 z-10 flex flex-wrap items-center gap-2 rounded-lg border border-accent/40 bg-accent/8 px-3 py-2"
    >
      <span className="tabular text-sm font-medium">{count} selected</span>
      <Button size="sm" onClick={onShortlist}>
        <Star size={14} aria-hidden="true" /> Shortlist
      </Button>
      <Button size="sm" onClick={onApplied}>
        <Check size={14} aria-hidden="true" /> Mark applied
      </Button>
      <Button size="sm" onClick={onStatus}>
        Set status…
      </Button>
      <Button size="sm" onClick={onLabels}>
        <Tag size={14} aria-hidden="true" /> Labels…
      </Button>
      <Button size="sm" onClick={onBlacklist}>
        <Ban size={14} aria-hidden="true" /> Blacklist…
      </Button>
      <Button size="sm" variant="ghost" onClick={onDelete}>
        <Trash2 size={14} aria-hidden="true" /> Delete…
      </Button>
      <Button
        size="sm"
        variant="ghost"
        onClick={onClear}
        className="ml-auto"
        aria-label="Clear selection"
      >
        <X size={14} aria-hidden="true" /> Clear
      </Button>
    </div>
  );
}
