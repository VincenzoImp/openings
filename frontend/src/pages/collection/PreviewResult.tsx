import { formatTime } from "../../api";
import { Tag } from "../../design";
import { plural } from "../../library/common";
import type { Preview } from "./model";

/** What a preview found, what each provider answered and what a run would cost. */
export function PreviewResult({ preview }: { preview: Preview }) {
  return (
    <section className="sub" aria-live="polite" aria-labelledby="preview-title">
      <h3 id="preview-title">
        Preview: {plural(preview.total, "match", "matches")}
      </h3>
      {(preview.request_estimate || preview.full_request_estimate) && (
        <p className="caption">
          {preview.request_estimate &&
            `About ${preview.request_estimate.total} requests for this preview (up to 3 results per portal). `}
          {preview.full_request_estimate &&
            `A full run: about ${preview.full_request_estimate.total} requests before cache reuse.`}
        </p>
      )}
      {!!preview.diagnostics?.length && (
        <ul className="plain tagged">
          {preview.diagnostics.map((item, index) => (
            <li key={index}>
              <Tag tone={item.state === "error" ? "danger" : "neutral"}>
                {item.provider}
              </Tag>{" "}
              {item.message || plural(item.requests || 0, "request")}
              {item.next_run_at
                ? ` · next try ${formatTime(item.next_run_at)}`
                : ""}
            </li>
          ))}
        </ul>
      )}
      <ul className="list">
        {preview.items.slice(0, 6).map((item, index) => (
          <li key={index}>
            <div className="grow">
              <span className="title">{item.title}</span>
              <div className="meta">
                {[item.company, item.location].filter(Boolean).join(" · ")}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
