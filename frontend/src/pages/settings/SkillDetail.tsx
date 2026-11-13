import { useEffect, useRef, useState } from "react";
import { Button, Dialog, ErrorBanner, Loading, Tag } from "../../design";
import { fileSize, plural } from "../../library/common";
import { useFresh } from "../../library/useFresh";
import { body, linkedFiles, type SkillItem, type SkillText } from "./model";
import { SkillNotes } from "./SkillNotes";

/** One file of a skill, read-only, as the agent reads it. */
function FileDialog({
  skill,
  path,
  onClose,
}: {
  skill: string;
  path: string;
  onClose: () => void;
}) {
  const file = useFresh<SkillText | null>(
    `/skills/${skill}/files/${path}`,
    null,
    [],
  );
  return (
    <Dialog title={`${skill}/${path}`} onClose={onClose} className="wide">
      {file.error ? (
        <ErrorBanner message={file.error} retry={file.reload} />
      ) : file.data ? (
        <pre
          className="code wrap skill-text"
          tabIndex={0}
          aria-label={`Text of ${skill}/${path}`}
        >
          {file.data.content}
        </pre>
      ) : (
        <Loading label="Loading the file…" />
      )}
    </Dialog>
  );
}

/**
 * A served skill: its local notes, its text and its reference files. The
 * shipped text cannot be changed here; it comes with the server's version.
 */
export function SkillDetail({
  skill,
  release,
  focus,
}: {
  skill: SkillItem;
  release?: string;
  focus: boolean;
}) {
  const text = useFresh<SkillText | null>(
    `/skills/${skill.name}?local_notes=false`,
    null,
    [],
  );
  const [reading, setReading] = useState<{
    skill: string;
    path: string;
  } | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (focus) heading.current?.focus();
  }, [focus, skill.name]);
  const content = text.data ? body(text.data.content) : "";
  const files = (
    skill.file_details ||
    skill.files.map((path) => ({ path, bytes: 0, title: "" }))
  ).filter((file) => file.path !== "SKILL.md");
  const linked = linkedFiles(text.data?.content || "", skill.name);
  return (
    <section className="card detail skill" aria-labelledby="skill-title">
      <header className="top">
        <div className="grow">
          <h2 id="skill-title" tabIndex={-1} ref={heading}>
            {skill.name}
          </h2>
          <div className="muted">{skill.description}</div>
        </div>
        <Tag>Read-only{release ? ` · ${release}` : ""}</Tag>
      </header>
      <div className="sub local-notes">
        <SkillNotes skill={skill.name} />
      </div>
      <div className="sub">
        <div className="spread">
          <h3>Skill text</h3>
          <span className="caption">
            <span className="mono">SKILL.md</span>
            {content && ` · ${plural(content.split("\n").length, "line")}`} ·
            read-only
          </span>
        </div>
        {text.error ? (
          <ErrorBanner message={text.error} retry={text.reload} />
        ) : text.data ? (
          <pre
            className="code wrap skill-text"
            tabIndex={0}
            aria-label={`Text of the ${skill.name} skill`}
          >
            {content}
          </pre>
        ) : (
          <Loading label="Loading the skill…" />
        )}
      </div>
      <div className="sub">
        <h3>Reference files</h3>
        {files.length || linked.length ? (
          <ul className="list" aria-label="Reference files">
            {files.map((file) => (
              <li key={file.path}>
                <div className="grow">
                  <span className="title mono">{file.path}</span>
                  {file.title && <div className="meta">{file.title}</div>}
                </div>
                {!!file.bytes && (
                  <span className="caption num">{fileSize(file.bytes)}</span>
                )}
                <Button
                  size="sm"
                  variant="quiet"
                  aria-label={`Read ${file.path}`}
                  onClick={() =>
                    setReading({ skill: skill.name, path: file.path })
                  }
                >
                  Read
                </Button>
              </li>
            ))}
            {linked.map((file) => (
              <li key={`${file.skill}/${file.path}`}>
                <div className="grow">
                  <span className="title mono">{file.path}</span>
                  <div className="meta">Shared from {file.skill}</div>
                </div>
                <Button
                  size="sm"
                  variant="quiet"
                  aria-label={`Read ${file.skill}/${file.path}`}
                  onClick={() => setReading(file)}
                >
                  Read
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">This skill has no reference file.</p>
        )}
      </div>
      {reading && (
        <FileDialog
          skill={reading.skill}
          path={reading.path}
          onClose={() => setReading(null)}
        />
      )}
    </section>
  );
}
