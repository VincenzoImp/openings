import { useEffect, useRef } from "react";
import { Button, ErrorBanner, Loading, Stepper } from "../design";
import { PageHead } from "../library/common";
import { markSetup, setupMark } from "../shell/setup";
import { useUrlState } from "../state";
import { ConnectStep } from "./setup/ConnectStep";
import { firstStep, setupComplete, steps, type StepId } from "./setup/model";
import { NextStep } from "./setup/NextStep";
import { RecordStep } from "./setup/Record";
import { useSetup } from "./setup/useSetup";

const STEPS: { id: StepId; label: string }[] = [
  { id: "agent", label: "Connect your agent" },
  { id: "record", label: "Your record" },
  { id: "next", label: "First applications" },
];

/**
 * The setup guide: connect an agent, watch it build the record (or fill in
 * the basics by hand) and see what happens next. Every state is read from the
 * workspace; `#setup?step=…` opens a step. A new workspace opens here first.
 */
export default function SetupPage() {
  const setup = useSetup();
  const [chosen, choose] = useUrlState("step", "");
  // Without a step in the address the guide opens where the workspace stands,
  // once, so it does not move while the agent works.
  const start = useRef<StepId | null>(null);
  if (!setup.loading && !start.current) start.current = firstStep(setup.facts);
  const step = (
    STEPS.some((item) => item.id === chosen) ? chosen : start.current
  ) as StepId;
  const state = steps(setup.facts);
  const complete = !setup.loading && setupComplete(setup.facts);
  useEffect(() => {
    if (complete && setupMark() === "started") markSetup("done");
  }, [complete]);
  const skip = () => {
    markSetup(complete ? "done" : "skipped");
    location.hash = "#today";
  };
  return (
    <div className="setup">
      <PageHead
        title="Set up your workspace"
        actions={
          <Button variant="quiet" onClick={skip}>
            {complete ? "Go to Today" : "Skip for now"}
          </Button>
        }
      >
        Openings is operated by your own AI agent. Connect it once; it then
        builds your career record with you and prepares your first applications.
        You can fill in the basics yourself as well.
      </PageHead>
      {setup.error && (
        <ErrorBanner message={setup.error} retry={setup.reload} />
      )}
      {setup.loading ? (
        <Loading label="Reading your workspace…" />
      ) : (
        <Stepper
          id="setup"
          label="Set-up steps"
          value={step}
          onChange={choose}
          steps={STEPS.map((item) => ({ ...item, ...state[item.id] }))}
        >
          {step === "agent" ? (
            <ConnectStep
              tokens={setup.facts.tokens}
              onContinue={() => choose("record")}
            />
          ) : step === "record" ? (
            <RecordStep
              facts={setup.facts}
              profile={setup.profile}
              preferences={setup.preferences}
              onNext={() => choose("next")}
            />
          ) : (
            <NextStep applications={setup.facts.applications} />
          )}
        </Stepper>
      )}
      <p className="caption">
        Prefer to do it without an agent? Fill in the basics under Your record,
        then add entries and claims in <a href="#profile">Profile</a> and your
        templates in <a href="#templates">Templates</a>. You can connect an
        agent later in <a href="#settings">Settings</a>, and open this guide
        again from Settings, Workspace.
      </p>
    </div>
  );
}
