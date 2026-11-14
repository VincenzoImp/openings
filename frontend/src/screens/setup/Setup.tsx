import { usePreferences, useProfile } from "../../query/setup";
import { useTitle } from "../../shell/context";
import { href, navigate, useRoute } from "../../shell/router";
import { SkeletonRows } from "../../ui/Page";
import { Stepper } from "./Frame";
import { AboutStep, CvStep, DoneStep, JobsStep } from "./Steps";
import { STEPS, stepOf, type StepId } from "./model";
import "./setup.css";

/**
 * The first-run guide (#setup?step=…): About you, Find jobs, Your CV, Done.
 * It opens after the password is set on a new workspace and again from
 * Today's checklist or Settings. Every step writes through an existing
 * operation; Find jobs and Your CV can be skipped, About you needs a name.
 */
export default function Setup() {
  const route = useRoute();
  const step = stepOf(route.query.get("step"));
  const index = STEPS.findIndex((item) => item.id === step);
  // On a phone the top bar names the step.
  useTitle(STEPS[index].label);
  const profile = useProfile();
  const preferences = usePreferences();
  const go = (to: StepId | "today") =>
    navigate(to === "today" ? href("today") : href("setup", {}, { step: to }));
  const next = () => go(STEPS[index + 1]?.id ?? "today");
  const back = index > 0 ? () => go(STEPS[index - 1].id) : undefined;

  const ready = profile.data && preferences.data;
  return (
    <div className="setup">
      <Stepper current={index} />
      {!ready ? (
        <div className="setup-card">
          <SkeletonRows rows={4} />
        </div>
      ) : step === "about" ? (
        <AboutStep
          key="about"
          profile={profile.data!}
          preferences={preferences.data!}
          onNext={next}
        />
      ) : step === "jobs" ? (
        <JobsStep
          key="jobs"
          preferences={preferences.data!}
          onNext={next}
          onBack={back}
        />
      ) : step === "cv" ? (
        <CvStep key="cv" onNext={next} onBack={back} />
      ) : (
        <DoneStep key="done" onBack={back} onFinish={() => go("today")} />
      )}
    </div>
  );
}
