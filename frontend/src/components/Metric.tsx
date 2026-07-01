import { Card, CardContent } from "@heroui/react";

/** A single labelled metric tile used across the analytics and cleanup pages. */
export function Metric({ label, value }: { label: string; value: number }) {
  return (
    <Card className="border border-slate-200 shadow-sm" variant="default">
      <CardContent className="grid min-h-24 gap-2 p-4">
        <span className="text-xs font-bold uppercase text-slate-500">{label}</span>
        <strong className="text-3xl font-semibold leading-none text-slate-950">
          {value}
        </strong>
      </CardContent>
    </Card>
  );
}
