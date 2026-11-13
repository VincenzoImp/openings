import { Tabs } from "../design";
import { PageHead } from "../library/common";
import { useUrlFilters } from "../state";
import { Insights } from "./applications/Insights";
import { DEFAULTS, type Filters } from "./applications/model";
import { Pipeline } from "./applications/Pipeline";

/**
 * Every application from its shortlist to the employer's reply: the
 * pipeline as a list or a board, and Insights from the employers' answers.
 * `#applications?stage=…` opens a stage and `section=insights` the insights;
 * the shell rewrites the old page's `status=` and `readiness=ready`
 * (shell/routes.ts).
 */
export default function ApplicationsPage() {
  const [values, setValues] = useUrlFilters({ ...DEFAULTS, section: "" });
  const { section, ...filters } = values;
  const insights = section === "insights";
  return (
    <>
      <PageHead title="Applications">
        Every attempt, from the shortlist to the employer's reply. You send each
        application yourself; here you record what happened.
      </PageHead>
      <Tabs
        id="applications"
        label="Applications views"
        value={insights ? "insights" : "pipeline"}
        onChange={(id) =>
          setValues({ section: id === "insights" ? "insights" : "" })
        }
        items={[
          { id: "pipeline", label: "Pipeline" },
          { id: "insights", label: "Insights" },
        ]}
      >
        {insights ? (
          <Insights />
        ) : (
          <Pipeline
            filters={filters as Filters}
            setFilters={(patch) => setValues(patch as Record<string, string>)}
          />
        )}
      </Tabs>
    </>
  );
}
