import { Button } from "../../ui/Button";
import { ToneText } from "../../ui/Badge";
import { jobOf } from "../applications/data";
import { closedSummary, followUpLine } from "../applications/model";
import { SentDocuments, useCurrentDocuments } from "./Documents";
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
 * Applied, Interview, Offer and Closed: the status line first, Record reply
 * (not when Closed), then the notes, the history, the documents that were
 * sent, and the posting, requirements and answers folded and read-only.
 * Never an empty document slot.
 */
export function FollowUp({ context }: { context: PageContext }) {
  const { app, noReplyDays } = context;
  const current = useCurrentDocuments(app.id);
  const closed = app.status === "closed";
  const line = closed
    ? { text: closedSummary(app) }
    : followUpLine(app, noReplyDays);
  const requirements = app.requirements ?? [];
  const questions = app.questions ?? [];
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
        <Fold title="Posting">
          <PostingText text={jobOf(app).posting} />
        </Fold>
        {(requirements.length > 0 || questions.length > 0) && (
          <Fold
            title="Requirements and answers"
            count={requirements.length + questions.length}
          >
            {requirements.length > 0 && (
              <Requirements app={app} editable={false} />
            )}
            <Answers app={app} />
          </Fold>
        )}
      </div>
    </>
  );
}
