import { AlertDialog, Button } from "@heroui/react";
import { useEffect } from "react";

export interface ConfirmDialogProps {
  confirmLabel: string;
  description: string;
  isOpen: boolean;
  isPending?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  title: string;
}

export function ConfirmDialog({
  confirmLabel,
  description,
  isOpen,
  isPending = false,
  onCancel,
  onConfirm,
  title
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isPending) {
        onCancel();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isPending, onCancel]);

  if (!isOpen) {
    return null;
  }

  return (
    <AlertDialog
      isOpen={isOpen}
      onOpenChange={(open) => {
        if (!open) {
          onCancel();
        }
      }}
    >
      <AlertDialog.Trigger className="sr-only" aria-hidden="true" />
      <AlertDialog.Backdrop isDismissable isKeyboardDismissDisabled={false} variant="blur">
        <AlertDialog.Container placement="center" size="md">
          <AlertDialog.Dialog>
            <AlertDialog.Header>
              <AlertDialog.Icon status="danger" />
              <AlertDialog.Heading>{title}</AlertDialog.Heading>
            </AlertDialog.Header>
            <AlertDialog.Body>{description}</AlertDialog.Body>
            <AlertDialog.Footer>
              <Button isDisabled={isPending} onPress={onCancel} variant="outline">
                Cancel
              </Button>
              <Button autoFocus isDisabled={isPending} onPress={onConfirm} variant="danger">
                {confirmLabel}
              </Button>
            </AlertDialog.Footer>
          </AlertDialog.Dialog>
        </AlertDialog.Container>
      </AlertDialog.Backdrop>
    </AlertDialog>
  );
}
