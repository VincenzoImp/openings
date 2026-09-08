import { Dialog } from "../components/Dialog";
import { Kbd } from "../components/Kbd";

const GROUPS: { title: string; keys: [string, string][] }[] = [
  {
    title: "Everywhere",
    keys: [
      ["1 … 5", "Inbox, Pipeline, Companies, Runs, System"],
      ["n", "Add a posting by hand"],
      ["?", "This help"],
      ["Esc", "Close dialog or go back"],
    ],
  },
  {
    title: "Lists",
    keys: [
      ["j / k", "Next / previous job"],
      ["Enter", "Open the job page"],
      ["o", "Open the posting in a new tab"],
      ["s", "Shortlist"],
      ["a", "Mark applied"],
      ["x", "Blacklist (asks first)"],
      ["l", "Edit labels"],
      ["/", "Search"],
    ],
  },
  {
    title: "Pipeline",
    keys: [
      ["← / →", "Previous / next column"],
      ["[ / ]", "Move the job one status back / forward"],
    ],
  },
];

export function HelpDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} title="Keyboard shortcuts" onClose={onClose}>
      <div className="grid gap-4 sm:grid-cols-2">
        {GROUPS.map((group) => (
          <div key={group.title}>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              {group.title}
            </h3>
            <dl className="flex flex-col gap-1">
              {group.keys.map(([key, description]) => (
                <div key={key} className="flex items-center gap-2 text-sm">
                  <dt className="w-16 shrink-0">
                    <Kbd>{key}</Kbd>
                  </dt>
                  <dd className="text-slate-700">{description}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </Dialog>
  );
}
