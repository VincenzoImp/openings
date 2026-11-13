import { useState } from "react";
import {
  api,
  type Application,
  type BulkResult,
  type ListResult,
} from "../../api";
import { Button, Dialog, ErrorBanner, Loading } from "../../design";
import { plural } from "../../library/common";
import { useFresh } from "../../library/useFresh";
import { useWorkspace } from "../../state";

/**
 * "Close 3 as no reply": the Applied applications sent longer ago than the
 * no-reply period, listed before they are closed as no_response today.
 */
export function CloseNoReply({
  due,
  days,
  size = "sm",
}: {
  /** How many applications wait past the period. */
  due: number;
  days: number;
  size?: "sm" | "md";
}) {
  const [open, setOpen] = useState(false);
  if (!due) return null;
  return (
    <>
      <Button size={size} onClick={() => setOpen(true)}>
        Close {due} as no reply
      </Button>
      {open && <Confirm days={days} onClose={() => setOpen(false)} />}
    </>
  );
}

function Confirm({ days, onClose }: { days: number; onClose: () => void }) {
  const { mutate, pending, notify } = useWorkspace();
  const list = useFresh<ListResult<Application>>(
    "/applications?no_reply_due=true&sort=applied&limit=200",
    { items: [], total: 0 },
    ["applications"],
  );
  const items = list.data.items;
  async function close() {
    let result: BulkResult | undefined;
    const ok = await mutate(
      async () => {
        result = await api<BulkResult>("/applications/bulk", "POST", {
          action: "close",
          outcome: "no_response",
          items: items.map((item) => ({
            id: item.id,
            expected_version: item.version,
          })),
        });
      },
      `${plural(items.length, "application")} closed as no reply.`,
    );
    if (ok && result?.failed)
      notify(
        `${result.succeeded} closed; ${result.failed} could not be: ${result.items.find((item) => item.error)?.error?.message}`,
        true,
      );
    if (ok) onClose();
  }
  return (
    <Dialog
      title={`Close ${plural(items.length || 0, "application")} as no reply?`}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Keep them open</Button>
          <Button
            variant="primary"
            disabled={pending || list.loading || !items.length}
            onClick={close}
          >
            Close as no reply
          </Button>
        </>
      }
    >
      <div className="stack">
        <p>
          These were sent more than {days} days ago and the employer has not
          answered. They close today with the outcome No reply; you can reopen
          one if an answer arrives.
        </p>
        {list.error ? (
          <ErrorBanner message={list.error} retry={list.reload} />
        ) : list.loading ? (
          <Loading label="Loading applications…" />
        ) : (
          <ul className="plain">
            {items.map((item) => (
              <li key={item.id}>
                {item.job?.title} · {item.job?.company}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Dialog>
  );
}
