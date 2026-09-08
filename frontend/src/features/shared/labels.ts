import type { AttachmentKind, EventKind, JobStatus } from "../../api/types";

export type Tone = "neutral" | "muted" | "info" | "accent" | "positive" | "warning" | "negative";

export const STATUS_LABELS: Record<JobStatus, string> = {
  new: "New",
  shortlisted: "Shortlisted",
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  blacklisted: "Blacklisted",
};

export const STATUS_TONE: Record<JobStatus, Tone> = {
  new: "neutral",
  shortlisted: "info",
  applied: "accent",
  interviewing: "warning",
  offer: "positive",
  rejected: "negative",
  withdrawn: "muted",
  blacklisted: "muted",
};

export const ATTACHMENT_LABELS: Record<AttachmentKind, string> = {
  cv: "CV",
  cover_letter: "Cover Letter",
  form_answers: "Form Answers",
  other: "Other",
};

export const EVENT_TONE: Record<EventKind, Tone> = {
  ingested: "neutral",
  posting: "neutral",
  status: "info",
  label: "accent",
  note: "warning",
  attachment: "positive",
  updated: "neutral",
  merged: "warning",
};

export const EVENT_LABELS: Record<EventKind, string> = {
  ingested: "Ingested",
  posting: "Posting",
  status: "Status",
  label: "Label",
  note: "Note",
  attachment: "Attachment",
  updated: "Edited",
  merged: "Merged",
};
