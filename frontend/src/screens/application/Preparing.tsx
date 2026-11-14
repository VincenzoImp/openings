import { useRef } from "react";
import { Check, Circle, ListChecks, Minus, Upload } from "lucide-react";
import { Button } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import { ActionBar } from "../../ui/Split";
import { jobOf } from "../applications/data";
import { checklist, firstMissing } from "../applications/model";
import {
  DocumentSlot,
  KIND_LABEL,
  useCurrentDocuments,
  useDocumentUpload,
  type Kind,
} from "./Documents";
import type { PageContext } from "./Page";
import {
  Answers,
  Fold,
  HistoryList,
  PinnedNote,
  PostingText,
  Requirements,
  Section,
} from "./Sections";

const STATE_ICON = { done: Check, missing: Circle, not_needed: Minus };

/**
 * Shortlisted, preparing: what is missing before Ready, the slots of the
 * required documents, the requirements and the form's answers. The primary
 * action settles the first missing item; once nothing is, the page is Ready.
 */
export function Preparing({ context }: { context: PageContext }) {
  const { app } = context;
  const current = useCurrentDocuments(app.id);
  const required = (app.required_documents ?? ["cv", "letter"]) as Kind[];
  const uploaders = {
    cv: useDocumentUpload(app.id, "cv", current.cv),
    letter: useDocumentUpload(app.id, "letter", current.letter),
  };
  const requirements = useRef<HTMLDivElement>(null);
  const first = firstMissing(app);
  const items = checklist(app);
  const resolve = () => {
    requirements.current?.scrollIntoView({ block: "center" });
    requirements.current
      ?.querySelector<HTMLInputElement>("input[type=checkbox]:not(:checked)")
      ?.focus();
  };
  const primary =
    first === "cv" || first === "letter" ? (
      <Button
        variant="primary"
        icon={Upload}
        disabled={uploaders[first].busy}
        onClick={uploaders[first].open}
      >
        Upload {first === "cv" ? "CV" : "letter"}
      </Button>
    ) : first === "requirement" ? (
      <Button variant="primary" icon={ListChecks} onClick={resolve}>
        Resolve requirements
      </Button>
    ) : null;
  const posting = jobOf(app).posting;
  return (
    <>
      {context.header(primary)}
      <div className="apg-prep">
        <div className="apg-main">
          <Section id="missing" title="What's missing">
            <ul className="ap-checklist">
              {items.map((item) => (
                <li key={item.key} data-state={item.state}>
                  <Icon icon={STATE_ICON[item.state]} size="sm" />
                  <span>{item.label}</span>
                  <span className="ap-muted">
                    {item.state === "not_needed"
                      ? "not needed"
                      : (item.detail ??
                        (item.state === "done" ? "uploaded" : "missing"))}
                  </span>
                </li>
              ))}
            </ul>
          </Section>
          <div className="apg-slots" data-count={required.length}>
            {required.map((kind) => (
              <DocumentSlot
                key={kind}
                kind={kind}
                revision={current[kind]}
                revisions={current.revisions}
                loading={current.loading}
                uploader={uploaders[kind]}
              />
            ))}
          </div>
          <div ref={requirements}>
            <Section id="requirements" title="Requirements">
              <Requirements app={app} />
            </Section>
          </div>
          {(app.questions ?? []).length > 0 && (
            <div className="ap-section">
              <Answers app={app} />
            </div>
          )}
          <Fold title="Notes and history">
            <PinnedNote app={app} />
            <HistoryList app={app} />
          </Fold>
          <div className="apg-posting-fold">
            <Fold title="Posting">
              <PostingText text={posting} />
            </Fold>
          </div>
        </div>
        <aside className="apg-side" aria-label="Posting">
          <h2 className="ap-section-title">Posting</h2>
          <PostingText text={posting} />
        </aside>
      </div>
      {primary && (
        <ActionBar>
          {first === "cv" || first === "letter" ? (
            <Button
              variant="primary"
              icon={Upload}
              disabled={uploaders[first].busy}
              onClick={uploaders[first].open}
            >
              Upload {KIND_LABEL[first]}
            </Button>
          ) : (
            <Button variant="primary" onClick={resolve}>
              Resolve requirements
            </Button>
          )}
        </ActionBar>
      )}
    </>
  );
}
