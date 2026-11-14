// Reading pasted CV text (plain text or Markdown) into a header and career
// entries with their highlights, for the import preview. Nothing is stored
// here: the result goes through the career import preview and is added only
// when the person confirms. Pure, so it is tested directly.
import type { Dates, Kind } from "./model";

export interface ParsedEntry {
  kind: Kind;
  title: string;
  organization: string;
  dates: Dates | null;
  location: string;
  narrative: string;
  skills: string[];
  highlights: string[];
}
export interface ParsedHeader {
  name?: string;
  headline?: string;
  location?: string;
  email?: string;
  phone?: string;
  summary?: string;
  links?: { label: string; url: string }[];
}
export interface ParsedCv {
  header: ParsedHeader;
  entries: ParsedEntry[];
}

type Section = Kind | "summary" | "skills" | "header";

const HEADINGS: [RegExp, Section][] = [
  [/^(summary|profile|about( me)?|objective|introduction)$/, "summary"],
  [
    /^((work |professional |relevant )?experience|employment( history)?|work history|career)$/,
    "experience",
  ],
  [/^(education|studies|academic background)$/, "education"],
  [/^(courses?|certifications?|training)$/, "course"],
  [/^((selected |side |personal )?projects?)$/, "project"],
  [/^(awards?|honou?rs|prizes?)$/, "award"],
  [/^(publications?|papers|talks)$/, "publication"],
  [/^(languages?)$/, "language"],
  [/^((technical |core )?skills|technologies|tools|expertise)$/, "skills"],
];

function sectionOf(heading: string): Section {
  const text = heading
    .toLowerCase()
    .replace(/[:*_#]/g, "")
    .trim();
  for (const [pattern, section] of HEADINGS)
    if (pattern.test(text)) return section;
  return "other";
}

const EMAIL = /[\w.+-]+@[\w-]+(\.[\w-]+)+/;
const PHONE = /^\+?[\d\s().-]{7,}$/;
const URL_LIKE = /^(https?:\/\/)?([\w-]+\.)+[a-z]{2,}(\/\S*)?$/i;
const BULLET = /^\s*(?:[-*•‣–]|\d+[.)])\s+/;

const MONTH = (name: string) => {
  const index = "janfebmaraprmayjunjulaugsepoctnovdec".indexOf(
    name.slice(0, 3).toLowerCase(),
  );
  return index < 0 || index % 3 ? "" : String(index / 3 + 1).padStart(2, "0");
};
const POINT =
  /(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+)?((?:19|20)\d{2})(?:[-/.](0[1-9]|1[0-2]))?|(0?[1-9]|1[0-2])\/((?:19|20)\d{2})/i;
const RANGE = new RegExp(
  `(${POINT.source})(?:\\s*(?:–|—|-|to|until)\\s*(present|current|now|today|ongoing|${POINT.source}))?`,
  "i",
);

function point(text: string) {
  const match = POINT.exec(text);
  if (!match) return "";
  if (match[5]) return `${match[5]}-${match[4].padStart(2, "0")}`;
  const month = match[1] ? MONTH(match[1]) : match[3] || "";
  return month ? `${match[2]}-${month}` : match[2];
}

/** The dates in a line and the line without them. */
export function readDates(line: string): { dates: Dates | null; rest: string } {
  const match = RANGE.exec(line);
  if (!match) return { dates: null, rest: line };
  const start = point(match[1]);
  const tail = match[0].slice(match[1].length);
  const endText = tail.replace(/^\s*(?:–|—|-|to|until)\s*/i, "");
  const rest = (
    line.slice(0, match.index) + line.slice(match.index + match[0].length)
  )
    .replace(/\(\s*\)|\[\s*\]/g, "")
    .replace(/\s*[|·,]\s*$/, "")
    .replace(/^\s*[|·,]\s*/, "")
    .trim();
  if (!tail.trim()) return { dates: { kind: "single", start }, rest };
  if (/^(present|current|now|today|ongoing)$/i.test(endText.trim()))
    return { dates: { kind: "period", start, current: true }, rest };
  const end = point(endText);
  if (!end || end < start) return { dates: { kind: "single", start }, rest };
  return { dates: { kind: "period", start, end, current: false }, rest };
}

const strip = (text: string) =>
  text
    .replace(/\*\*|__|`/g, "")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1 ($2)")
    .trim();

/** "Title — Organization", "Title at Organization", "Title, Organization". */
function splitTitle(text: string) {
  const parts = text.split(/\s+(?:—|–|-|\||@|at)\s+|\s*,\s+/);
  if (parts.length < 2) return { title: text, organization: "", more: "" };
  return {
    title: parts[0],
    organization: parts[1],
    more: parts.slice(2).join(", "),
  };
}

function blankEntry(kind: Kind, heading: string): ParsedEntry {
  const { dates, rest } = readDates(heading);
  const { title, organization, more } = splitTitle(rest);
  return {
    kind,
    title,
    organization,
    dates,
    location: more,
    narrative: "",
    skills: [],
    highlights: [],
  };
}

/** Header lines: contacts separated by "·", "|" or ",", and a headline. */
function readHeaderLine(line: string, header: ParsedHeader) {
  const parts = line
    .split(/\s+[·|•]\s+|\s{2,}/)
    .map(strip)
    .filter(Boolean);
  const plain: string[] = [];
  for (const part of parts) {
    const email = EMAIL.exec(part);
    if (email && !header.email) header.email = email[0];
    else if (PHONE.test(part) && !header.phone) header.phone = part;
    else if (URL_LIKE.test(part.replace(/\s*\(.*\)$/, ""))) {
      const url = part.replace(/^.*\((.*)\)$/, "$1");
      (header.links ??= []).push({
        label: part.replace(/\s*\(.*\)$/, ""),
        url: /^https?:/.test(url) ? url : `https://${url}`,
      });
    } else plain.push(part);
  }
  if (!plain.length) return;
  if (!header.headline && parts.length === plain.length && parts.length === 1)
    header.headline = plain[0];
  else if (!header.location) header.location = plain.join(", ");
}

/**
 * Read a CV. Headings ("## Experience") open sections; within one, a
 * sub-heading or a bold line opens an entry, a line with dates gives its
 * dates and place, bullets are its highlights and other lines its
 * description. Lines before the first section form the header.
 */
export function parseCv(text: string): ParsedCv {
  const header: ParsedHeader = {};
  const entries: ParsedEntry[] = [];
  const summary: string[] = [];
  let section: Section = "header";
  let entry: ParsedEntry | null = null;
  let headerLines = 0;

  const close = () => {
    if (entry && entry.title) {
      entry.narrative = entry.narrative.trim();
      entries.push(entry);
    }
    entry = null;
  };

  for (const raw of text.replace(/\r\n?/g, "\n").split("\n")) {
    const line = raw.trim();
    if (!line || /^(-{3,}|\*{3,}|_{3,})$/.test(line)) continue;
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    const bold = /^(\*\*|__)(.+?)\1\s*(.*)$/.exec(line);
    const level = heading ? heading[1].length : 0;

    // The name: the first top heading, or the first line of plain text.
    if (section === "header" && !header.name && (level === 1 || !heading)) {
      if (level === 1 || (headerLines === 0 && !BULLET.test(line))) {
        header.name = strip(heading ? heading[2] : line);
        headerLines++;
        continue;
      }
    }
    // A section: a heading, or a short line that names one ("EXPERIENCE").
    const named =
      heading && level <= 2
        ? sectionOf(heading[2])
        : !heading && line.length < 40 && !BULLET.test(line)
          ? sectionOf(line)
          : "other";
    if ((heading && level <= 2) || (!heading && named !== "other")) {
      close();
      section = named;
      continue;
    }
    if (section === "header") {
      headerLines++;
      readHeaderLine(line, header);
      continue;
    }
    if (section === "summary") {
      summary.push(strip(line.replace(BULLET, "")));
      continue;
    }
    if (section === "skills") {
      const items = strip(line.replace(BULLET, ""))
        .replace(/^[^:]{1,40}:\s*/, "")
        .split(/\s*[,;·|]\s*/)
        .filter(Boolean);
      let skills = entries.find((item) => item.kind === "skill");
      if (!skills) {
        skills = { ...blankEntry("skill", "Skills"), title: "Skills" };
        entries.push(skills);
      }
      for (const item of items)
        if (!skills.skills.some((s) => s.toLowerCase() === item.toLowerCase()))
          skills.skills.push(item);
      continue;
    }
    const kind: Kind = section;
    // A new entry: a sub-heading, or a bold line.
    if (heading || bold) {
      close();
      entry = blankEntry(
        kind,
        strip(heading ? heading[2] : `${bold![2]} ${bold![3]}`),
      );
      continue;
    }
    if (BULLET.test(line)) {
      const textOf = strip(line.replace(BULLET, ""));
      // In Languages or Awards a bullet is an entry of its own, as it is
      // before any entry of a section.
      if (!entry || kind === "language" || kind === "award") {
        close();
        entry = blankEntry(kind, textOf);
        close();
        continue;
      }
      const skillLine = /^(skills|tech(nologies)?|stack|tools)\s*:\s*/i;
      if (skillLine.test(textOf))
        entry.skills.push(
          ...textOf
            .replace(skillLine, "")
            .split(/\s*[,;·]\s*/)
            .filter(Boolean),
        );
      else entry.highlights.push(textOf);
      continue;
    }
    if (!entry) {
      entry = blankEntry(kind, strip(line));
      continue;
    }
    const current: ParsedEntry = entry;
    const { dates, rest } = readDates(strip(line));
    if (dates && !current.dates && rest.length < 60) {
      current.dates = dates;
      const parts = rest.split(/\s*[·|,]\s*/).filter(Boolean);
      if (!current.organization && parts.length > 1)
        current.organization = parts.shift()!;
      if (parts.length && !current.location)
        current.location = parts.join(", ");
      continue;
    }
    if (
      !current.organization &&
      !current.narrative &&
      !current.highlights.length &&
      line.length < 80 &&
      !/[.!?]$/.test(line)
    ) {
      current.organization = strip(line);
      continue;
    }
    current.narrative += (current.narrative ? "\n" : "") + strip(line);
  }
  close();
  if (summary.length) header.summary = summary.join("\n");
  for (const key of Object.keys(header) as (keyof ParsedHeader)[])
    if (!header[key] || (Array.isArray(header[key]) && !header[key]!.length))
      delete header[key];
  return { header, entries };
}

export const EXAMPLE = `# Alex Morgan
Data engineer
Zurich · alex@example.com · example.dev

## Summary
Six years building data pipelines for utilities.

## Experience
### Data engineer — Northwind Energy
2021 – Present · Zurich
- Built pipelines that process 40 million readings a day.
- Cut reporting time by 70%.

## Education
### MSc Computer Science — Example University
2017 – 2019`;
