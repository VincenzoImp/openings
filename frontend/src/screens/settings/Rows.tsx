import { useId, type ReactNode } from "react";

/** A section of Settings: its heading, an optional one-line lead, its rows. */
export function SettingsSection({
  title,
  lead,
  children,
}: {
  title: string;
  lead?: ReactNode;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <section className="set-section" aria-labelledby={id}>
      <h2 id={id} className="set-title">
        {title}
      </h2>
      {lead && <p className="set-lead">{lead}</p>}
      {children}
    </section>
  );
}

/** A group of rows under a smaller heading: "Automatic backups". */
export function SettingsGroup({
  title,
  note,
  children,
}: {
  title: string;
  note?: ReactNode;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <section className="set-group" aria-labelledby={id}>
      <h3 id={id} className="set-group-title">
        {title}
        {note}
      </h3>
      {children}
    </section>
  );
}

/** One setting: its name and a line on what it does, then its control. */
export function SettingRow({
  title,
  note,
  children,
  control,
}: {
  title: string;
  /** Beside the title: Owner only. */
  note?: ReactNode;
  children?: ReactNode;
  control?: ReactNode;
}) {
  return (
    <div className="set-row">
      <div className="set-row-text">
        <p className="set-row-title">
          {title}
          {note}
        </p>
        {children && <p className="set-row-desc">{children}</p>}
      </div>
      {control && <div className="set-row-control">{control}</div>}
    </div>
  );
}
