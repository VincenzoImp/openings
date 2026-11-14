import { useRef } from "react";
import { Upload } from "lucide-react";
import { Button } from "../../ui/Button";
import { ActionBar } from "../../ui/Split";
import { jobOf } from "../applications/data";
import { firstMissing } from "../applications/model";
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

/**
 * Shortlisted, preparing: the required documents, the requirements and the
 * form's answers. What is missing is said once, in the head; the primary
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
  const resolve = () => {
    requirements.current?.scrollIntoView({ block: "center" });
    requirements.current
      ?.querySelector<HTMLInputElement>("input[type=checkbox]:not(:checked)")
      ?.focus();
  };
  const action =
    first === "cv" || first === "letter" ? (
      <Button
        variant="primary"
        icon={Upload}
        disabled={uploaders[first].busy}
        onClick={uploaders[first].open}
      >
        Upload {KIND_LABEL[first]}
      </Button>
    ) : first === "requirement" ? (
      <Button variant="primary" onClick={resolve}>
        Resolve requirements
      </Button>
    ) : null;
  const posting = jobOf(app).posting;
  return (
    <>
      {context.header(action)}
      <div className="apg-prep">
        <div className="apg-main">
          {required.length > 0 && (
            <Section id="documents" title="Documents">
              <div className="apg-slots">
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
            </Section>
          )}
          <div ref={requirements}>
            <Section id="requirements" title="Requirements">
              <Requirements app={app} />
            </Section>
          </div>
          {(app.questions ?? []).length > 0 && (
            <Section id="answers" title="Form answers">
              <Answers app={app} />
            </Section>
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
      {action && <ActionBar>{action}</ActionBar>}
    </>
  );
}
