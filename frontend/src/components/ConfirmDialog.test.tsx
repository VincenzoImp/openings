import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ConfirmDialog } from "./ConfirmDialog";

test("cancels the confirm dialog with Escape", () => {
  const onCancel = vi.fn();

  render(
    <ConfirmDialog
      confirmLabel="Confirm delete"
      description="This cannot be undone."
      isOpen
      onCancel={onCancel}
      onConfirm={vi.fn()}
      title="Delete selected jobs permanently?"
    />
  );

  expect(screen.getByRole("alertdialog", { name: "Delete selected jobs permanently?" })).toBeInTheDocument();

  fireEvent.keyDown(document, { key: "Escape" });

  expect(onCancel).toHaveBeenCalledTimes(1);
});
