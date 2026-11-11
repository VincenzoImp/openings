/** Links from an Activity record (change, question, request) to the record it is about. */
export type Open = (id: string) => void;
export interface Links {
  onOpenJob: Open;
  onOpenApplication: Open;
}
export const subjectNames: Record<string, string> = {
  job: "Job",
  application: "Application",
  knowledge: "Career entry",
  claim: "Claim",
  template: "Template",
  source: "Source",
  collection_run: "Collection run",
  collection: "Collection settings",
  provider: "Provider",
  task: "Collection task",
  profile: "Profile",
  instructions: "Instructions",
  note: "Note",
  context: "Context",
  document: "Document",
  file: "File",
  question: "Question",
  request: "Request",
  token: "API token",
  workspace: "Workspace",
};
const sections: Record<string, string> = {
  knowledge: "#career?section=knowledge",
  claim: "#career?section=claims",
  profile: "#career",
  template: "#templates?section=templates",
  instructions: "#templates",
  source: "#collection",
  collection: "#collection",
  collection_run: "#collection",
  provider: "#collection",
  task: "#collection",
  token: "#settings?section=agents",
  workspace: "#settings",
};
export function RecordLink({
  type,
  id,
  jobId,
  applicationId,
  label,
  onOpenJob,
  onOpenApplication,
}: Links & {
  type?: string | null;
  id?: string | null;
  jobId?: string | null;
  applicationId?: string | null;
  label?: string;
}) {
  const name = subjectNames[type || ""] || "Record";
  const text = label ? `${name}: ${label}` : name;
  if (applicationId)
    return (
      <button
        type="button"
        className="inline-link"
        onClick={() => onOpenApplication(applicationId)}
      >
        {text}
      </button>
    );
  if (jobId)
    return (
      <button
        type="button"
        className="inline-link"
        onClick={() => onOpenJob(jobId)}
      >
        {text}
      </button>
    );
  if (id && sections[type || ""])
    return (
      <a className="inline-link" href={sections[type || ""]}>
        {text}
      </a>
    );
  return <span>{type ? text : ""}</span>;
}
