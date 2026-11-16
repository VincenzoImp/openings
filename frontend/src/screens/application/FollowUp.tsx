import { Button } from "../../ui/Button";
import { Disclosure } from "../../ui/Disclosure";
import { ToneText } from "../../ui/Badge";
import { jobOf } from "../applications/data";
import { closedSummary, followUpLine } from "../applications/model";
import { SentDocuments, useCurrentDocuments } from "./Documents";
import type { PageContext } from "./Page";
import {
  Answers,
  HistoryList,
  PinnedNote,
  PostingText,
  Requirements,
  Section,
} from "./Sections";

/**
 * Applied, Interview, Offer and Closed: the status line first, Record reply
 * (not when Closed), then the notes, the history, the documents that were
 * sent, and the requirements and answers folded and read-only. The posting
 * is beside them on a wide screen, as while Shortlisted, and folded below
 * them otherwise. Never an empty document slot.
 */
export function FollowUp({ context }: { context: PageContext }) {
  const { app, noReplyDays } = context;
  const current = useCurrentDocuments(app.id);
  const closed = app.stage === "closed";
  const line = closed
    ? { text: closedSummary(app) }
    : followUpLine(app, noReplyDays);
  const requirements = app.requirements ?? [];
  const questions = app.questions ?? [];
  const posting = jobOf(app).posting;
  return (
    <>
      {context.header(
        closed ? null : (
          <Button
            variant="primary"
            kbd="R"
            onClick={() => context.open("reply")}
          >
            Record reply
          </Button>
        ),
      )}
      <div className="apg-prep">
        <div className="apg-follow">
          <p className="apg-statusline" role="status">
            <ToneText tone={line.tone}>{line.text}</ToneText>
          </p>
          <div className="ap-section">
            <PinnedNote app={app} />
          </div>
          <Section id="history" title="History">
            <HistoryList app={app} />
          </Section>
          <SentDocuments current={current} />
          <div className="apg-posting-fold">
            <Disclosure className="ap-fold" title="Posting">
              <PostingText text={posting} />
            </Disclosure>
          </div>
          {(requirements.length > 0 || questions.length > 0) && (
            <Disclosure
              className="ap-fold"
              title="Requirements and answers"
              note={requirements.length + questions.length}
            >
              {requirements.length > 0 && (
                <Requirements app={app} editable={false} />
              )}
              <Answers app={app} />
            </Disclosure>
          )}
        </div>
        <aside className="apg-side" aria-label="Posting">
          <h2 className="ap-section-title">Posting</h2>
          <PostingText text={posting} />
        </aside>
      </div>
    </>
  );
}
