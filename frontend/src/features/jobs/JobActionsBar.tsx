import { Button } from "@heroui/react";
import { Bookmark, Check, Download, Trash2, X } from "lucide-react";

import type { ExportFormat } from "../../api/types";

interface JobActionsBarProps {
  canGoBack: boolean;
  canGoForward: boolean;
  exportFormat: ExportFormat;
  isAppliedPending: boolean;
  isBlacklistPending: boolean;
  isBookmarkPending: boolean;
  isDeletePending: boolean;
  isExportPending: boolean;
  isLoading: boolean;
  jobsCount: number;
  onBlacklistSelected: () => void;
  onDeleteSelected: () => void;
  onExportFiltered: () => void;
  onExportFormatChange: (format: ExportFormat) => void;
  onExportSelected: () => void;
  onMarkAppliedSelected: () => void;
  onMarkNotAppliedSelected: () => void;
  onNextPage: () => void;
  onPreviousPage: () => void;
  onPageSizeChange: (pageSize: number) => void;
  onSaveSelected: () => void;
  onUnsaveSelected: () => void;
  page: number;
  pageCount: number;
  pageSize: number;
  selectedCount: number;
}

export function JobActionsBar({
  canGoBack,
  canGoForward,
  exportFormat,
  isAppliedPending,
  isBlacklistPending,
  isBookmarkPending,
  isDeletePending,
  isExportPending,
  isLoading,
  jobsCount,
  onBlacklistSelected,
  onDeleteSelected,
  onExportFiltered,
  onExportFormatChange,
  onExportSelected,
  onMarkAppliedSelected,
  onMarkNotAppliedSelected,
  onNextPage,
  onPageSizeChange,
  onPreviousPage,
  onSaveSelected,
  onUnsaveSelected,
  page,
  pageCount,
  pageSize,
  selectedCount
}: JobActionsBarProps) {
  const hasSelection = selectedCount > 0;

  return (
    <div className="grid w-full min-w-0 gap-3">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap gap-2">
          <label className="flex items-center gap-2 text-sm font-medium text-zinc-700">
            <span>Export</span>
            <select
              aria-label="Export format"
              className="h-9 min-w-0 rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950 shadow-sm outline-none focus:border-zinc-950 focus:ring-2 focus:ring-zinc-100"
              onChange={(event) => onExportFormatChange(event.target.value as ExportFormat)}
              value={exportFormat}
            >
              <option value="csv">CSV</option>
              <option value="json">JSON</option>
            </select>
          </label>
          <Button isDisabled={isExportPending || jobsCount === 0} onPress={onExportFiltered} variant="outline">
            <Download aria-hidden="true" size={16} />
            Export filtered
          </Button>
          <Button isDisabled={!hasSelection || isExportPending} onPress={onExportSelected} variant="outline">
            <Download aria-hidden="true" size={16} />
            Export selected
          </Button>
          <Button isDisabled={!hasSelection || isBookmarkPending} onPress={onSaveSelected} variant="outline">
            <Bookmark aria-hidden="true" size={16} />
            Save selected
          </Button>
          <Button isDisabled={!hasSelection || isBookmarkPending} onPress={onUnsaveSelected} variant="outline">
            <Bookmark aria-hidden="true" size={16} />
            Unsave selected
          </Button>
          <Button isDisabled={!hasSelection || isAppliedPending} onPress={onMarkAppliedSelected} variant="outline">
            <Check aria-hidden="true" size={16} />
            Mark applied
          </Button>
          <Button
            isDisabled={!hasSelection || isAppliedPending}
            onPress={onMarkNotAppliedSelected}
            variant="outline"
          >
            <Check aria-hidden="true" size={16} />
            Mark not applied
          </Button>
        </div>
        <div className="flex min-w-0 flex-wrap gap-2">
          <Button
            isDisabled={!hasSelection || isBlacklistPending}
            onPress={onBlacklistSelected}
            variant={hasSelection ? "danger" : "outline"}
          >
            <Trash2 aria-hidden="true" size={16} />
            Blacklist selected
          </Button>
          <Button
            isDisabled={!hasSelection || isDeletePending}
            onPress={onDeleteSelected}
            variant={hasSelection ? "danger" : "outline"}
          >
            <X aria-hidden="true" size={16} />
            Delete selected
          </Button>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm text-zinc-600" aria-label="Pagination">
        <label className="flex items-center gap-2 text-sm font-medium text-zinc-700">
          <span>Rows</span>
          <select
            aria-label="Page size"
            className="h-9 min-w-0 rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950 shadow-sm outline-none focus:border-zinc-950 focus:ring-2 focus:ring-zinc-100"
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
            value={pageSize}
          >
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={200}>200</option>
          </select>
        </label>
        <Button isDisabled={!canGoBack || isLoading} onPress={onPreviousPage} variant="outline">
          Previous page
        </Button>
        <span className="min-w-24 text-center">
          Page {page + 1} of {pageCount}
        </span>
        <Button isDisabled={!canGoForward || isLoading} onPress={onNextPage} variant="outline">
          Next page
        </Button>
      </div>
    </div>
  );
}
