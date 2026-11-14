import { Tabs } from "../design";
import { PageHead } from "../library/common";
import { useUrlFilters } from "../state";
import { DEFAULTS, type Filters } from "./applications/model";
import { Pipeline } from "./applications/Pipeline";
import { Stats } from "./applications/Stats";

/**
 * Every application from its first Draft to the employer's answer: the
 * pipeline, and Stats on the applications sent. `#applications?stage=…`
 * opens a stage and `section=stats` the stats.
 */
export default function ApplicationsPage() {
  const [values, setValues] = useUrlFilters({ ...DEFAULTS, section: "" });
  const { section, ...filters } = values;
  const stats = section === "stats";
  return (
    <>
      <PageHead title="Applications">
        Every attempt, from the first Draft to the employer's answer. You send
        each application yourself; here you record what happened.
      </PageHead>
      <Tabs
        id="applications"
        label="Applications views"
        value={stats ? "stats" : "pipeline"}
        onChange={(id) => setValues({ section: id === "stats" ? "stats" : "" })}
        items={[
          { id: "pipeline", label: "Pipeline" },
          { id: "stats", label: "Stats" },
        ]}
      >
        {stats ? (
          <Stats />
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
