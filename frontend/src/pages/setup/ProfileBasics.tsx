import type { FormEvent } from "react";
import { api, type Profile } from "../../api";
import { Button, Field } from "../../design";
import { useWorkspace } from "../../state";

/**
 * The first fields of the Profile. Career, Profile has the rest: phone,
 * summary, links and other details.
 */
export function ProfileBasics({
  profile,
  onDone,
}: {
  profile: Profile;
  onDone: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "").trim();
    if (
      await mutate(
        () =>
          api("/career/profile", "PATCH", {
            expected_version: profile.version,
            name: text("name"),
            headline: text("headline"),
            location: text("location"),
            email: text("email"),
          }),
        "Profile saved.",
      )
    )
      onDone();
  }
  return (
    <form
      key={profile.version}
      className="stack"
      aria-label="Profile basics"
      onSubmit={save}
    >
      <div className="form-grid">
        <Field label="Name">
          <input
            name="name"
            required
            maxLength={200}
            autoComplete="name"
            defaultValue={profile.name}
          />
        </Field>
        <Field label="Headline" hint="What you do, in a few words.">
          <input
            name="headline"
            maxLength={500}
            defaultValue={profile.headline}
            placeholder="Senior data engineer"
          />
        </Field>
        <Field label="Location">
          <input
            name="location"
            maxLength={300}
            autoComplete="address-level2"
            defaultValue={profile.location}
          />
        </Field>
        <Field label="Email">
          <input
            name="email"
            type="email"
            maxLength={300}
            autoComplete="email"
            defaultValue={profile.email}
          />
        </Field>
      </div>
      <div className="row">
        <Button variant="primary" size="sm" disabled={pending}>
          Save the profile
        </Button>
        <a className="btn quiet sm" href="#career">
          The whole profile in Career
        </a>
      </div>
    </form>
  );
}
