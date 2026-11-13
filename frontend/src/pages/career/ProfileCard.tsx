import { useState, type FormEvent } from "react";
import { api, type Json, type Profile } from "../../api";
import {
  Button,
  ErrorBanner,
  Field,
  IconButton,
  KeyValueEditor,
  Loading,
} from "../../design";
import { useResource, useWorkspace } from "../../state";

const blank: Profile = {
  name: "",
  headline: "",
  location: "",
  email: "",
  phone: "",
  summary: "",
  links: [],
  metadata: {},
  version: 1,
};
interface Link {
  label: string;
  url: string;
}
const linkOf = (item: unknown): Link =>
  typeof item === "string"
    ? { label: "Website", url: item }
    : {
        label: String((item as Json)?.label ?? ""),
        url: String((item as Json)?.url ?? ""),
      };

/** The Profile: who the owner is, with typed fields and free-form details. */
export function ProfileCard() {
  const { data, loading, error, reload } = useResource<Profile>(
    "/career/profile",
    blank,
  );
  if (error) return <ErrorBanner message={error} retry={reload} />;
  if (loading) return <Loading label="Loading the profile…" />;
  return <ProfileForm key={data.version} profile={data} />;
}

function ProfileForm({ profile }: { profile: Profile }) {
  const { mutate, pending, notify } = useWorkspace();
  const [links, setLinks] = useState(() => profile.links.map(linkOf));
  const [details, setDetails] = useState<{
    value: Json;
    problem: string | null;
  }>({ value: profile.metadata, problem: null });
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (details.problem) return notify(details.problem, true);
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "");
    await mutate(
      () =>
        api("/career/profile", "PATCH", {
          expected_version: profile.version,
          name: text("name"),
          headline: text("headline"),
          location: text("location"),
          email: text("email"),
          phone: text("phone"),
          summary: text("summary"),
          links: links.filter((link) => link.url.trim()),
          metadata: details.value,
        }),
      "Profile saved.",
    );
  }
  const setLink = (index: number, patch: Partial<Link>) =>
    setLinks((rows) =>
      rows.map((row, at) => (at === index ? { ...row, ...patch } : row)),
    );
  return (
    <form
      className="card block"
      aria-labelledby="profile-title"
      onSubmit={save}
    >
      <header>
        <h2 id="profile-title" className="grow">
          Profile
        </h2>
        <span className="caption only-desktop">Version {profile.version}</span>
        <Button variant="primary" size="sm" disabled={pending}>
          Save profile
        </Button>
      </header>
      <div className="body form-grid">
        <Field label="Name">
          <input name="name" defaultValue={profile.name} autoComplete="name" />
        </Field>
        <Field label="Headline">
          <input name="headline" defaultValue={profile.headline} />
        </Field>
        <Field label="Location">
          <input name="location" defaultValue={profile.location} />
        </Field>
        <Field label="Email">
          <input
            name="email"
            type="email"
            defaultValue={profile.email}
            autoComplete="email"
          />
        </Field>
        <Field label="Phone">
          <input
            name="phone"
            type="tel"
            defaultValue={profile.phone}
            autoComplete="tel"
          />
        </Field>
        <Field
          label="Summary"
          hint="Used at the top of a CV when the template has a summary."
          className="wide"
        >
          <textarea name="summary" rows={3} defaultValue={profile.summary} />
        </Field>
        <fieldset className="field wide">
          <legend>Links</legend>
          <div className="kv">
            {links.map((link, index) => (
              <div className="kv-row link-row" key={index}>
                <input
                  className="input"
                  aria-label={`Link ${index + 1} label`}
                  placeholder="Website, LinkedIn…"
                  value={link.label}
                  onChange={(event) =>
                    setLink(index, { label: event.target.value })
                  }
                />
                <input
                  className="input"
                  type="url"
                  aria-label={`Link ${index + 1} URL`}
                  placeholder="https://…"
                  value={link.url}
                  onChange={(event) =>
                    setLink(index, { url: event.target.value })
                  }
                />
                <IconButton
                  icon="close"
                  label={`Remove link ${index + 1}`}
                  data-dirty-control="true"
                  onClick={() =>
                    setLinks((rows) => rows.filter((_, at) => at !== index))
                  }
                />
              </div>
            ))}
            <div>
              <Button
                type="button"
                size="sm"
                icon="plus"
                data-dirty-control="true"
                onClick={() =>
                  setLinks((rows) => [...rows, { label: "", url: "" }])
                }
              >
                Add a link
              </Button>
            </div>
          </div>
        </fieldset>
        <p className="caption wide">
          Target roles, preferences, decision rules, eligibility and writing
          rules are items in your <a href="#policy">Policy</a>.
        </p>
        <fieldset className="field wide">
          <legend>Other details</legend>
          <p className="caption">
            Free-form values the product does not act on.
          </p>
          <KeyValueEditor
            label="Other profile details as keys and values"
            value={profile.metadata}
            onChange={(value, problem) => setDetails({ value, problem })}
          />
        </fieldset>
      </div>
    </form>
  );
}
