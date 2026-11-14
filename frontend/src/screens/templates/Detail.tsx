import { useState } from "react";
import {
  CircleCheck,
  Clock,
  Copy,
  Download,
  Ellipsis,
  FileText,
  Paperclip,
  PenLine,
  Trash2,
} from "lucide-react";
import { save } from "../../api/client";
import {
  Button,
  IconButton,
  ConfirmDialog,
  Dialog,
  Field,
  Input,
  formatDate,
  MetaLine,
  SkeletonRows,
  DetailBar,
  DetailBody,
  Tabs,
  useToast,
} from "../../ui";
import { SheetMenu } from "../../ui";
import {
  useDeleteTemplate,
  useDuplicateTemplate,
  useTemplate,
  useUpdateTemplate,
  type Template,
} from "../../query/templates";
import { FilesTab } from "./Files";
import { LimitsTab } from "./Limits";
import { PreviewTab } from "./Preview";
import { SourceTab } from "./Source";
import { TABS, changedText, copyName, kindLabel, type Tab } from "./model";

/** One template: its header actions and the Preview · Source · Files · Limits tabs. */
export function TemplateDetail({
  id,
  summary,
  names,
  tab,
  onTab,
  onBack,
  onSelect,
  onDirty,
}: {
  id: string;
  /** The list's copy, shown while the full record loads. */
  summary: Template;
  names: string[];
  tab: Tab;
  onTab: (tab: Tab) => void;
  onBack: () => void;
  onSelect: (id: string | null) => void;
  onDirty: (dirty: boolean) => void;
}) {
  const query = useTemplate(id);
  const template = query.data ?? summary;
  const full = query.data;
  const toast = useToast();
  const update = useUpdateTemplate(full);
  const remove = useDeleteTemplate();
  const duplicate = useDuplicateTemplate();
  const [renaming, setRenaming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const kind = kindLabel(template.kind);
  const files = template.file_count ?? 0;
  const fail = (cause: unknown) =>
    toast.show({
      tone: "error",
      message: cause instanceof Error ? cause.message : "That did not work.",
    });
  const menu = [
    {
      id: "rename",
      label: "Rename",
      icon: PenLine,
      onSelect: () => setRenaming(true),
    },
    {
      id: "duplicate",
      label: "Duplicate",
      icon: Copy,
      disabled: duplicate.isPending,
      onSelect: () =>
        duplicate.mutate(
          { template, name: copyName(template.name, names) },
          {
            onSuccess: (copy) => {
              toast.show({
                tone: "success",
                message: `Created “${copy.name}”`,
              });
              onSelect(copy.id);
            },
            onError: fail,
          },
        ),
    },
    {
      id: "download",
      label: "Download source",
      icon: Download,
      disabled: !full,
      onSelect: () =>
        full &&
        save(
          new Blob([full.tex ?? ""], { type: "application/x-tex" }),
          `${template.name.replace(/[^\w.-]+/g, "-").toLowerCase() || "template"}.tex`,
        ),
    },
    "separator" as const,
    {
      id: "delete",
      label: "Delete permanently…",
      icon: Trash2,
      danger: true,
      onSelect: () => setDeleting(true),
    },
  ];
  return (
    <>
      <DetailBar onBack={onBack} backLabel="Back to templates">
        <SheetMenu
          label={`Template ${template.name}`}
          items={menu}
          trigger={(props) => (
            <IconButton
              {...props}
              icon={Ellipsis}
              label="More actions"
              tooltip="none"
            />
          )}
        />
      </DetailBar>
      <DetailBody className="tpl-detail">
        <header className="tpl-head">
          <h2 className="tpl-title">{template.name}</h2>
          <MetaLine
            items={[
              { icon: FileText, text: kind, label: "Kind" },
              {
                icon: Paperclip,
                text: files === 1 ? "1 file" : `${files} files`,
                label: "Files",
              },
              {
                icon: Clock,
                text: changedText(formatDate(template.updated_at)),
                label: "Changed",
              },
              ...(template.is_default
                ? [{ icon: CircleCheck, text: `Default ${kind}` }]
                : []),
            ]}
          />
          {!template.is_default && (
            <div className="tpl-actions">
              <Button
                disabled={!full || update.isPending}
                onClick={() =>
                  update.mutate(
                    { is_default: true },
                    {
                      onSuccess: () =>
                        toast.show({
                          tone: "success",
                          message: `“${template.name}” is the default ${kind}`,
                        }),
                      onError: fail,
                    },
                  )
                }
              >
                Set as default
              </Button>
            </div>
          )}
        </header>
        <Tabs
          label="Template"
          idPrefix="template"
          items={TABS.map((item) => ({
            id: item.id,
            label: item.label,
            count: item.id === "files" && files ? files : undefined,
          }))}
          value={tab}
          onChange={(value) => onTab(value as Tab)}
          className="tpl-tabs"
        />
        <div
          className="tpl-panel"
          id="template-panel"
          role="tabpanel"
          aria-labelledby={`template-tab-${tab}`}
        >
          {!full ? (
            <SkeletonRows rows={4} />
          ) : tab === "preview" ? (
            <PreviewTab template={full} />
          ) : tab === "source" ? (
            <SourceTab template={full} onDirty={onDirty} />
          ) : tab === "files" ? (
            <FilesTab template={full} />
          ) : (
            <LimitsTab template={full} onDirty={onDirty} />
          )}
        </div>
      </DetailBody>
      <RenameDialog
        open={renaming}
        template={template}
        saving={update.isPending}
        onClose={() => setRenaming(false)}
        onSave={(name) =>
          update.mutate(
            { name },
            {
              onSuccess: () => {
                setRenaming(false);
                toast.show({
                  tone: "success",
                  message: `Renamed to “${name}”`,
                });
              },
              onError: fail,
            },
          )
        }
      />
      <ConfirmDialog
        open={deleting}
        title={`Delete “${template.name}” permanently?`}
        confirm="Delete template"
        onClose={() => setDeleting(false)}
        onConfirm={() =>
          remove.mutate(template, {
            onSuccess: () => {
              toast.show({
                tone: "success",
                message: `Deleted “${template.name}”`,
              });
              onSelect(null);
            },
            onError: fail,
          })
        }
      >
        {`Its source${files ? ` and ${files === 1 ? "1 file" : `${files} files`}` : ""} are deleted. Documents already made from it keep their own copy. This cannot be undone.`}
      </ConfirmDialog>
    </>
  );
}

function RenameDialog({
  open,
  template,
  saving,
  onClose,
  onSave,
}: {
  open: boolean;
  template: Template;
  saving: boolean;
  onClose: () => void;
  onSave: (name: string) => void;
}) {
  const [name, setName] = useState(template.name);
  const [error, setError] = useState<string | null>(null);
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setName(template.name);
      setError(null);
    }
  }
  const submit = () => {
    const value = name.trim();
    if (!value) return setError("Give the template a name.");
    if (value === template.name) return onClose();
    onSave(value);
  };
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Rename template"
      initialFocus="input"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            type="submit"
            form="template-rename"
            disabled={saving}
          >
            Save
          </Button>
        </>
      }
    >
      <form
        id="template-rename"
        data-unguarded=""
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <Field label="Name" error={error}>
          <Input
            value={name}
            maxLength={200}
            onChange={(event) => {
              setName(event.target.value);
              setError(null);
            }}
          />
        </Field>
      </form>
    </Dialog>
  );
}
