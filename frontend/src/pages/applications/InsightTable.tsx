import type { ReactNode } from "react";
import type { InsightGroup } from "../../api";
import { Card, RateBar, percent } from "../../design";
import { plural } from "../../library/common";

/** "21% · 3", or the count alone when the rate is withheld. */
const rateText = (rate: number | null, count: number) =>
  rate === null ? String(count) : `${percent(rate)} · ${count}`;

/**
 * Sent applications of each group with how many got an answer and how many
 * led to an interview. A group below the minimum sample shows its counts and
 * says why there is no rate.
 */
export function InsightTable({
  title,
  name,
  groups,
  footer,
  empty,
}: {
  title: string;
  /** The heading of the first column: "Role family". */
  name: string;
  groups: InsightGroup[];
  footer?: ReactNode;
  empty?: string;
}) {
  return (
    <Card title={title} footer={footer}>
      {groups.length ? (
        <div className="datatable-wrap">
          <table className="datatable stack num">
            <thead>
              <tr>
                <th scope="col">{name}</th>
                <th scope="col" className="right">
                  Sent
                </th>
                <th scope="col">Got an answer</th>
                <th scope="col">Interview</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => (
                <tr key={group.key}>
                  <td className="primary">{group.label}</td>
                  <td className="right" data-label="Sent">
                    {group.sent}
                  </td>
                  {group.withheld ? (
                    <td colSpan={2} className="meta" data-label="Rate">
                      Too few to show a rate ·{" "}
                      {plural(group.responded, "answer")}
                    </td>
                  ) : (
                    <>
                      <td data-label="Got an answer">
                        <RateBar
                          rate={group.response_rate ?? 0}
                          count={group.responded}
                        />
                      </td>
                      <td data-label="Interview">
                        {rateText(group.interview_rate, group.interviews)}
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="body muted">{empty || "No sent application yet."}</p>
      )}
    </Card>
  );
}
