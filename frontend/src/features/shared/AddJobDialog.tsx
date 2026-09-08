import { useState } from "react";

import { JOB_STATUSES } from "../../api/types";
import type { JobStatus } from "../../api/types";
import { navigate } from "../../app/router";
import { Button } from "../../components/Button";
import { Dialog } from "../../components/Dialog";
import { Checkbox, Field, Input, Select, Textarea } from "../../components/Field";
import { STATUS_LABELS } from "./labels";
import { useJobCommands } from "./queries";

const EMPTY = {
  title: "",
  company: "",
  location: "",
  url: "",
  description: "",
  status: "shortlisted" as JobStatus,
  labels: "",
  jobType: "",
  level: "",
  remote: false,
  minAmount: "",
  maxAmount: "",
  currency: "",
  datePosted: "",
  companyUrl: "",
  note: "",
};

export function AddJobDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { addJob } = useJobCommands();
  const [form, setForm] = useState(EMPTY);
  const [more, setMore] = useState(false);
  const set = <K extends keyof typeof EMPTY>(key: K, value: (typeof EMPTY)[K]) =>
    setForm((current) => ({ ...current, [key]: value }));
  const valid = form.title.trim() !== "" && form.company.trim() !== "";

  const submit = () => {
    if (!valid) {
      return;
    }
    addJob.mutate(
      {
        title: form.title.trim(),
        company: form.company.trim(),
        location: form.location.trim(),
        job_url: form.url.trim() || null,
        description: form.description.trim() || null,
        status: form.status,
        labels: form.labels
          .split(",")
          .map((label) => label.trim())
          .filter(Boolean),
        job_type: form.jobType.trim() || null,
        job_level: form.level.trim() || null,
        is_remote: form.remote ? true : null,
        min_amount: form.minAmount ? Number(form.minAmount) : null,
        max_amount: form.maxAmount ? Number(form.maxAmount) : null,
        currency: form.currency.trim() || null,
        date_posted: form.datePosted || null,
        company_url: form.companyUrl.trim() || null,
        note: form.note.trim() || null,
      },
      {
        onSuccess: (result) => {
          setForm(EMPTY);
          setMore(false);
          onClose();
          if (result.job_ids[0]) {
            navigate({ jobId: result.job_ids[0] });
          }
        },
      },
    );
  };

  return (
    <Dialog
      open={open}
      title="Add a Posting"
      onClose={onClose}
      wide
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" disabled={!valid || addJob.isPending} onClick={submit}>
            {addJob.isPending ? "Adding…" : "Add Posting"}
          </Button>
        </>
      }
    >
      <form
        className="grid gap-3 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <Field label="Title" htmlFor="add-title">
          <Input
            id="add-title"
            name="title"
            value={form.title}
            onChange={(e) => set("title", e.target.value)}
            required
            autoComplete="off"
            autoFocus
          />
        </Field>
        <Field label="Company" htmlFor="add-company">
          <Input
            id="add-company"
            name="company"
            value={form.company}
            onChange={(e) => set("company", e.target.value)}
            required
            autoComplete="organization"
          />
        </Field>
        <Field label="Location" htmlFor="add-location">
          <Input
            id="add-location"
            name="location"
            value={form.location}
            onChange={(e) => set("location", e.target.value)}
            placeholder="City, Country or Remote"
          />
        </Field>
        <Field
          label="Posting URL"
          htmlFor="add-url"
          hint="Identifies the posting: the same URL updates instead of duplicating."
        >
          <Input
            id="add-url"
            name="url"
            type="url"
            inputMode="url"
            value={form.url}
            onChange={(e) => set("url", e.target.value)}
            placeholder="https://…"
          />
        </Field>
        <Field label="Status" htmlFor="add-status">
          <Select
            id="add-status"
            value={form.status}
            onChange={(e) => set("status", e.target.value as JobStatus)}
          >
            {JOB_STATUSES.filter((status) => status !== "blacklisted").map((value) => (
              <option key={value} value={value}>
                {STATUS_LABELS[value]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Labels" htmlFor="add-labels" hint="Comma separated">
          <Input
            id="add-labels"
            name="labels"
            value={form.labels}
            onChange={(e) => set("labels", e.target.value)}
            autoComplete="off"
          />
        </Field>
        <div className="sm:col-span-2">
          <Field label="Description (markdown)" htmlFor="add-description">
            <Textarea
              id="add-description"
              name="description"
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
              className="min-h-32"
            />
          </Field>
        </div>
        <div className="sm:col-span-2">
          <button
            type="button"
            className="text-xs text-accent underline"
            onClick={() => setMore((value) => !value)}
          >
            {more ? "Fewer fields" : "More fields…"}
          </button>
        </div>
        {more ? (
          <>
            <Field label="Job type" htmlFor="add-type">
              <Input
                id="add-type"
                value={form.jobType}
                onChange={(e) => set("jobType", e.target.value)}
                placeholder="fulltime, internship…"
              />
            </Field>
            <Field label="Level" htmlFor="add-level">
              <Input
                id="add-level"
                value={form.level}
                onChange={(e) => set("level", e.target.value)}
              />
            </Field>
            <Field label="Salary minimum" htmlFor="add-min">
              <Input
                id="add-min"
                type="number"
                inputMode="numeric"
                value={form.minAmount}
                onChange={(e) => set("minAmount", e.target.value)}
              />
            </Field>
            <Field label="Salary maximum" htmlFor="add-max">
              <Input
                id="add-max"
                type="number"
                inputMode="numeric"
                value={form.maxAmount}
                onChange={(e) => set("maxAmount", e.target.value)}
              />
            </Field>
            <Field label="Currency" htmlFor="add-currency">
              <Input
                id="add-currency"
                value={form.currency}
                onChange={(e) => set("currency", e.target.value)}
                placeholder="CHF, EUR, USD…"
              />
            </Field>
            <Field label="Posted on" htmlFor="add-date">
              <Input
                id="add-date"
                type="date"
                value={form.datePosted}
                onChange={(e) => set("datePosted", e.target.value)}
              />
            </Field>
            <Field label="Company URL" htmlFor="add-company-url">
              <Input
                id="add-company-url"
                type="url"
                inputMode="url"
                value={form.companyUrl}
                onChange={(e) => set("companyUrl", e.target.value)}
              />
            </Field>
            <div className="flex items-end pb-1">
              <Checkbox
                label="Remote"
                checked={form.remote}
                onChange={(e) => set("remote", e.target.checked)}
              />
            </div>
            <div className="sm:col-span-2">
              <Field label="First note" htmlFor="add-note">
                <Textarea
                  id="add-note"
                  value={form.note}
                  onChange={(e) => set("note", e.target.value)}
                />
              </Field>
            </div>
          </>
        ) : null}
      </form>
    </Dialog>
  );
}
