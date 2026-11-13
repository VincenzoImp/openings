import { useState } from "react";
import type { Preferences, Profile } from "../../api";
import { Banner, Button, Icon, Tag } from "../../design";
import { plural } from "../../library/common";
import { confirmLeave } from "../../state";
import { SourceEditor } from "../collection/SourceEditor";
import { recordItems, type ItemId, type SetupFacts } from "./model";
import { PreferenceBasics } from "./PreferenceBasics";
import { ProfileBasics } from "./ProfileBasics";

const STATE = {
  done: { tag: "Done", tone: "ready" },
  progress: { tag: "In progress", tone: "info" },
  todo: { tag: "Not started", tone: "neutral" },
} as const;
// Where each part of the record is kept in full.
const LOOK: Partial<Record<ItemId, string>> = {
  entries: "#career?section=knowledge",
  claims: "#career?section=claims",
  templates: "#templates",
};

/**
 * The record the agent builds, as a checklist read from the workspace. The
 * Profile, the Preferences basics and a first search can also be filled in here.
 */
export function RecordStep({
  facts,
  profile,
  preferences,
  questions,
  onNext,
}: {
  facts: SetupFacts;
  profile: Profile;
  preferences: Preferences;
  questions: number;
  onNext: () => void;
}) {
  const [open, setOpen] = useState<ItemId | null>(null);
  const toggle = (id: ItemId) => {
    if (open && !confirmLeave()) return;
    setOpen(open === id ? null : id);
  };
  const items = recordItems(facts);
  return (
    <section className="card" aria-labelledby="record-title">
      <header>
        <h2 id="record-title" className="grow">
          Your record
        </h2>
        <span className="caption">Your agent builds it with you</span>
      </header>
      {questions > 0 && (
        <div className="body">
          <Banner
            tone="attention"
            title={`Your agent has ${plural(questions, "question")} for you.`}
            action={
              <a className="btn sm" href="#activity">
                Answer the questions
              </a>
            }
          >
            It continues with what it can, and waits for your answers where it
            must.
          </Banner>
        </div>
      )}
      <ul className="list checklist" aria-label="Your record">
        {items.map((item, index) => {
          const formId = `setup-${item.id}`;
          const editable = ["profile", "preferences", "searches"].includes(
            item.id,
          );
          return (
            <li key={item.id}>
              <span className={`step-mark ${item.state}`} aria-hidden="true">
                {item.state === "done" ? <Icon name="check" /> : index + 1}
              </span>
              <div className="grow">
                <div className="title">{item.title}</div>
                <div className="meta">{item.meta}</div>
              </div>
              <div className="row checklist-actions">
                <Tag tone={STATE[item.state].tone}>{STATE[item.state].tag}</Tag>
                {editable ? (
                  <Button
                    size="sm"
                    variant={item.state === "done" ? "quiet" : ""}
                    aria-expanded={open === item.id}
                    aria-controls={open === item.id ? formId : undefined}
                    onClick={() => toggle(item.id)}
                  >
                    {item.id === "searches"
                      ? open === item.id
                        ? "Close the search form"
                        : "Add a search"
                      : open === item.id
                        ? "Close"
                        : item.state === "done"
                          ? "Edit"
                          : "Fill in"}
                    {item.id !== "searches" && (
                      <span className="sr">
                        {" "}
                        the {item.title.toLowerCase()}
                      </span>
                    )}
                  </Button>
                ) : (
                  <a className="btn quiet sm" href={LOOK[item.id]}>
                    Look
                    <span className="sr">
                      {" "}
                      at the {item.title.toLowerCase()}
                    </span>
                  </a>
                )}
              </div>
              {open === item.id && (
                <div id={formId} className="inline-form">
                  {item.id === "profile" ? (
                    <ProfileBasics
                      profile={profile}
                      onDone={() => setOpen(null)}
                    />
                  ) : item.id === "preferences" ? (
                    <PreferenceBasics
                      preferences={preferences}
                      noReply={facts.noReply}
                    />
                  ) : (
                    <SourceEditor search onClose={() => setOpen(null)} />
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <footer>
        <span className="muted grow">
          You can close this page. Your agent keeps working, and Today shows
          what it did.
        </span>
        <Button size="sm" onClick={onNext}>
          What happens next
        </Button>
      </footer>
    </section>
  );
}
