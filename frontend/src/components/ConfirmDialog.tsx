import { Button, Card, CardContent } from "@heroui/react";
import { AlertTriangle } from "lucide-react";

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
  if (!isOpen) {
    return null;
  }

  return (
    <div
      aria-modal="true"
      className="fixed inset-0 z-50 grid place-items-center bg-zinc-950/40 p-4"
      role="dialog"
    >
      <Card className="w-full max-w-md border border-red-200 shadow-xl" variant="default">
        <CardContent className="grid gap-5 p-5">
          <div className="flex items-start gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-md bg-red-50 text-red-700">
              <AlertTriangle aria-hidden="true" size={20} />
            </span>
            <div>
              <h2 className="text-lg font-semibold text-zinc-950">{title}</h2>
              <p className="mt-1 text-sm leading-6 text-zinc-600">{description}</p>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button isDisabled={isPending} onPress={onCancel} variant="outline">
              Cancel
            </Button>
            <Button isDisabled={isPending} onPress={onConfirm} variant="danger">
              {confirmLabel}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
