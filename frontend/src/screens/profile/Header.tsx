// The head of the CV (name, headline, contacts and links) and the summary:
// two blocks of the one Profile record, each edited on its own.
import { useState } from "react";
import { ExternalLink, Mail, MapPin, Phone, Plus, X } from "lucide-react";
import { Avatar } from "../../ui/Badge";
import { Button, IconButton } from "../../ui/Button";
import { Field, Input, Textarea } from "../../ui/Field";
import { Icon } from "../../ui/Icon";
import { EditBlock, ReadBlock, useEditing } from "./Block";
import { cached, writes, type Profile, type ProfileLink } from "./data";
import { linkHref, linkText } from "./model";
import { useBlockSave } from "./save";

type HeaderDraft = {
  name: string;
  headline: string;
  location: string;
  email: string;
  phone: string;
  links: ProfileLink[];
};

const linksOf = (profile: Profile): ProfileLink[] =>
  (profile.links ?? []).map((link) => ({
    label: String(link.label ?? ""),
    url: String(link.url ?? ""),
  }));

const headerOf = (profile: Profile): HeaderDraft => ({
  name: profile.name,
  headline: profile.headline,
  location: profile.location,
  email: profile.email,
  phone: profile.phone,
  links: linksOf(profile),
});

const TEXT = ["name", "headline", "location", "email", "phone"] as const;

const cleanLinks = (links: ProfileLink[]) =>
  links
    .filter((link) => link.url.trim())
    .map((link) => ({ label: link.label.trim(), url: link.url.trim() }));

/**
 * What the person changed since the block opened: only these fields are
 * saved, so a change made elsewhere to another field is kept.
 */
function headerPatch(draft: HeaderDraft, start: HeaderDraft) {
  const patch: Record<string, unknown> = {};
  for (const key of TEXT)
    if (draft[key].trim() !== start[key].trim()) patch[key] = draft[key].trim();
  const links = cleanLinks(draft.links);
  if (JSON.stringify(links) !== JSON.stringify(cleanLinks(start.links)))
    patch.links = links;
  return patch;
}

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function HeaderBlock({ profile }: { profile: Profile }) {
  const editing = useEditing();
  if (editing.open === "header") return <HeaderForm profile={profile} />;
  const contacts = [
    profile.location && { icon: MapPin, text: profile.location },
    profile.email && {
      icon: Mail,
      text: <a href={`mailto:${profile.email}`}>{profile.email}</a>,
    },
    profile.phone && {
      icon: Phone,
      text: (
        <a href={`tel:${profile.phone.replace(/\s/g, "")}`}>{profile.phone}</a>
      ),
    },
    ...linksOf(profile)
      .filter((link) => link.url)
      .map((link) => ({
        icon: ExternalLink,
        text: (
          <a href={linkHref(link.url)} target="_blank" rel="noreferrer">
            {linkText(link)}
          </a>
        ),
      })),
  ].filter(Boolean) as { icon: typeof Mail; text: React.ReactNode }[];
  const name = profile.name.trim();
  return (
    <ReadBlock
      name="header"
      className="pf-header"
      onEdit={() => editing.request("header")}
    >
      <div className="pf-header-top">
        {name && <Avatar name={name} size={56} />}
        <div className="pf-header-names">
          <p className="pf-name">
            {name || <span className="pf-missing">Add your name</span>}
          </p>
          {profile.headline && (
            <p className="pf-headline">{profile.headline}</p>
          )}
        </div>
      </div>
      {contacts.length > 0 && (
        <ul className="pf-contacts">
          {contacts.map((item, index) => (
            <li key={index}>
              <Icon icon={item.icon} size="sm" />
              <span>{item.text}</span>
            </li>
          ))}
        </ul>
      )}
    </ReadBlock>
  );
}

function HeaderForm({ profile }: { profile: Profile }) {
  const [start, setStart] = useState(() => headerOf(profile));
  const [draft, setDraft] = useState(start);
  const [base, setBase] = useState(profile.version);
  const [checked, setChecked] = useState(false);
  const patch = headerPatch(draft, start);
  const changes = Object.keys(patch).length;
  const emailError =
    draft.email.trim() && !EMAIL.test(draft.email.trim())
      ? "Write the whole address, for example alex@example.com."
      : undefined;
  const block = useBlockSave({
    write: (body: Record<string, unknown>) =>
      writes.profile({ ...body, expected_version: base }),
    saved: () => "Saved the header",
    onReload: () => {
      const stored = cached.profile();
      if (stored) {
        setStart(headerOf(stored));
        setDraft(headerOf(stored));
        setBase(stored.version);
      }
    },
    onKeepEditing: () => setBase(cached.profile()?.version ?? base),
  });
  const set =
    (key: (typeof TEXT)[number]) => (event: { target: { value: string } }) =>
      setDraft((value) => ({ ...value, [key]: event.target.value }));
  const setLink = (index: number, patch: Partial<ProfileLink>) =>
    setDraft((value) => ({
      ...value,
      links: value.links.map((link, at) =>
        at === index ? { ...link, ...patch } : link,
      ),
    }));
  return (
    <EditBlock
      title="Edit header"
      changes={changes}
      saving={block.saving}
      notice={block.notice}
      onSave={async () => {
        setChecked(true);
        if (emailError) {
          document.querySelector<HTMLElement>("[name=email]")?.focus();
          return false;
        }
        return block.save(patch);
      }}
    >
      <div className="pf-fields">
        <Field label="Name">
          <Input
            name="name"
            value={draft.name}
            onChange={set("name")}
            autoComplete="name"
            maxLength={200}
          />
        </Field>
        <Field label="Headline">
          <Input
            name="headline"
            value={draft.headline}
            onChange={set("headline")}
            maxLength={500}
          />
        </Field>
        <Field label="Location">
          <Input
            name="location"
            value={draft.location}
            onChange={set("location")}
            maxLength={300}
          />
        </Field>
        <Field label="Email" error={checked ? emailError : undefined}>
          <Input
            name="email"
            type="email"
            value={draft.email}
            onChange={set("email")}
            onBlur={() => setChecked(true)}
            autoComplete="email"
            maxLength={300}
          />
        </Field>
        <Field label="Phone">
          <Input
            name="phone"
            type="tel"
            value={draft.phone}
            onChange={set("phone")}
            autoComplete="tel"
            maxLength={100}
          />
        </Field>
      </div>
      <fieldset className="pf-links">
        <legend>Links</legend>
        {draft.links.map((link, index) => (
          <div className="pf-link-row" key={index}>
            <Input
              aria-label={`Link ${index + 1} label`}
              placeholder="Label"
              value={link.label}
              onChange={(event) =>
                setLink(index, { label: event.target.value })
              }
            />
            <Input
              aria-label={`Link ${index + 1} address`}
              placeholder="https://"
              type="url"
              value={link.url}
              onChange={(event) => setLink(index, { url: event.target.value })}
            />
            <IconButton
              icon={X}
              label={`Remove link ${index + 1}`}
              tooltip="none"
              onClick={() =>
                setDraft((value) => ({
                  ...value,
                  links: value.links.filter((_, at) => at !== index),
                }))
              }
            />
          </div>
        ))}
        <Button
          variant="ghost"
          size="sm"
          icon={Plus}
          onClick={() =>
            setDraft((value) => ({
              ...value,
              links: [...value.links, { label: "", url: "" }],
            }))
          }
        >
          Add link
        </Button>
      </fieldset>
    </EditBlock>
  );
}

export function SummaryBlock({ profile }: { profile: Profile }) {
  const editing = useEditing();
  if (editing.open === "summary") return <SummaryForm profile={profile} />;
  if (!profile.summary.trim())
    return (
      <Button
        variant="ghost"
        size="sm"
        icon={Plus}
        className="pf-add-inline"
        onClick={() => editing.request("summary")}
      >
        Add a summary
      </Button>
    );
  return (
    <ReadBlock name="summary" onEdit={() => editing.request("summary")}>
      <div className="pf-prose">
        {profile.summary.split(/\n{2,}/).map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      </div>
    </ReadBlock>
  );
}

function SummaryForm({ profile }: { profile: Profile }) {
  const [start, setStart] = useState(profile.summary);
  const [text, setText] = useState(start);
  const [base, setBase] = useState(profile.version);
  const block = useBlockSave({
    write: (body: { summary: string }) =>
      writes.profile({ expected_version: base, summary: body.summary.trim() }),
    saved: () => "Saved the summary",
    onReload: () => {
      const stored = cached.profile();
      if (stored) {
        setStart(stored.summary);
        setText(stored.summary);
        setBase(stored.version);
      }
    },
    onKeepEditing: () => setBase(cached.profile()?.version ?? base),
  });
  return (
    <EditBlock
      title="Edit summary"
      changes={text.trim() !== start.trim() ? 1 : 0}
      saving={block.saving}
      notice={block.notice}
      onSave={() => block.save({ summary: text })}
    >
      <Field label="Summary">
        <Textarea
          name="summary"
          rows={6}
          value={text}
          maxLength={20000}
          onChange={(event) => setText(event.target.value)}
        />
      </Field>
    </EditBlock>
  );
}
