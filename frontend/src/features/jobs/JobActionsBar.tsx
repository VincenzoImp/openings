import { Button } from "@heroui/react";
import { Bookmark, Check, Download, Trash2, X } from "lucide-react";

interface JobActionsBarProps {
  canGoBack: boolean;
  canGoForward: boolean;
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
  onExportSelected: () => void;
  onMarkAppliedSelected: () => void;
  onMarkNotAppliedSelected: () => void;
  onNextPage: () => void;
  onPreviousPage: () => void;
  onSaveSelected: () => void;
  onUnsaveSelected: () => void;
  page: number;
  pageCount: number;
  selectedCount: number;
}

export function JobActionsBar({
  canGoBack,
  canGoForward,
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
  onExportSelected,
  onMarkAppliedSelected,
  onMarkNotAppliedSelected,
  onNextPage,
  onPreviousPage,
  onSaveSelected,
  onUnsaveSelected,
  page,
  pageCount,
  selectedCount
}: JobActionsBarProps) {
  const hasSelection = selectedCount > 0;

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
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
        <div className="flex flex-wrap gap-2">
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
      <div className="flex items-center gap-2 text-sm text-zinc-600" aria-label="Pagination">
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
