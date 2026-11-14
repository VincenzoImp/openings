import { useRef, useState } from "react";
import {
  Download,
  Ellipsis,
  File as FileIcon,
  FileImage,
  FileText,
  FileType,
  Paperclip,
  Trash2,
  Upload,
  type LucideIcon,
} from "lucide-react";
import { save } from "../../api/client";
import {
  Button,
  IconButton,
  ConfirmDialog,
  formatDate,
  Icon,
  List,
  ListRow,
  ListRows,
  EmptyState,
  SkeletonRows,
  useToast,
} from "../../ui";
import { SheetMenu, usePhone } from "../../ui/ActionSheet";
import {
  fileBytes,
  useDeleteFile,
  useTemplateFiles,
  useUploadFiles,
  type Template,
  type TemplateFile,
} from "../../query/templates";
import { fileKind, fileSize } from "./model";

const ICONS: Record<string, LucideIcon> = {
  PDF: FileText,
  Font: FileType,
  Image: FileImage,
  "Class file": FileText,
  LaTeX: FileText,
  File: FileIcon,
};

/** Pick files and upload them to the template; returns the trigger. */
export function useFilePicker(template: Template, accept?: string) {
  const input = useRef<HTMLInputElement>(null);
  const upload = useUploadFiles(template.id);
  const toast = useToast();
  const picker = (
    <input
      ref={input}
      type="file"
      multiple={!accept}
      accept={accept}
      hidden
      aria-label="Files to upload"
      onChange={(event) => {
        const files = Array.from(event.target.files ?? []);
        event.target.value = "";
        if (!files.length) return;
        upload.mutate(files, {
          onSuccess: (count) =>
            toast.show({
              tone: "success",
              message:
                count === 1
                  ? `Uploaded “${files[0].name}”`
                  : `Uploaded ${count} files`,
            }),
          onError: (cause) =>
            toast.show({
              tone: "error",
              message:
                cause instanceof Error ? cause.message : "The upload failed.",
            }),
        });
      }}
    />
  );
  return { picker, open: () => input.current?.click(), busy: upload.isPending };
}

export async function downloadFile(file: TemplateFile) {
  const { blob } = await fileBytes(file);
  save(blob, file.name);
}

/** The files the source loads (fonts, images, class files) and a sample PDF. */
export function FilesTab({ template }: { template: Template }) {
  const files = useTemplateFiles(template.id);
  const { picker, open, busy } = useFilePicker(template);
  const remove = useDeleteFile();
  const toast = useToast();
  const [active, setActive] = useState<string | null>(null);
  const [removing, setRemoving] = useState<TemplateFile | null>(null);
  const items = files.data?.items ?? [];
  const phone = usePhone();
  const fail = (cause: unknown) =>
    toast.show({
      tone: "error",
      message: cause instanceof Error ? cause.message : "That did not work.",
    });
  return (
    <div className="tpl-files">
      {picker}
      {files.isPending ? (
        <SkeletonRows rows={3} />
      ) : !items.length ? (
        <EmptyState
          icon={Paperclip}
          title="No files yet"
          actions={
            <Button icon={Upload} onClick={open} disabled={busy}>
              {busy ? "Uploading…" : "Upload files"}
            </Button>
          }
        >
          Add the fonts, images and class files the source loads, and a sample
          PDF for Preview.
        </EmptyState>
      ) : (
        <>
          <div className="tpl-bar">
            <span className="tpl-bar-note">
              {items.length === 1 ? "1 file" : `${items.length} files`}
            </span>
            <span className="tpl-bar-space" />
            <Button size="sm" icon={Upload} onClick={open} disabled={busy}>
              {busy ? "Uploading…" : "Upload files"}
            </Button>
          </div>
          <List
            label="Files"
            className="tpl-file-list"
            activeId={active ?? items[0].id}
            onActiveChange={setActive}
            onOpen={(id) => {
              const file = items.find((item) => item.id === id);
              if (file) downloadFile(file).catch(fail);
            }}
          >
            <ListRows>
              {items.map((file) => {
                const kind = fileKind(file);
                return (
                  <ListRow
                    key={file.id}
                    id={file.id}
                    leading={<Icon icon={ICONS[kind] ?? FileIcon} size="sm" />}
                    title={file.name}
                    sub={`${kind} · ${fileSize(file.size)}`}
                    meta={
                      phone ? (
                        <SheetMenu
                          label={`File ${file.name}`}
                          items={[
                            {
                              id: "download",
                              label: "Download",
                              icon: Download,
                              onSelect: () =>
                                void downloadFile(file).catch(fail),
                            },
                            "separator",
                            {
                              id: "remove",
                              label: "Remove…",
                              icon: Trash2,
                              danger: true,
                              onSelect: () => setRemoving(file),
                            },
                          ]}
                          trigger={(props) => (
                            <IconButton
                              {...props}
                              icon={Ellipsis}
                              label={`More for ${file.name}`}
                              size="touch"
                              tooltip="none"
                            />
                          )}
                        />
                      ) : (
                        formatDate(file.created_at)
                      )
                    }
                    actions={[
                      {
                        label: `Download ${file.name}`,
                        icon: Download,
                        onClick: () => void downloadFile(file).catch(fail),
                      },
                      {
                        label: `Remove ${file.name}`,
                        icon: Trash2,
                        onClick: () => setRemoving(file),
                      },
                    ]}
                  />
                );
              })}
            </ListRows>
          </List>
        </>
      )}
      <ConfirmDialog
        open={removing !== null}
        title="Remove this file permanently?"
        confirm="Remove file"
        onClose={() => setRemoving(null)}
        onConfirm={() => {
          const file = removing;
          if (!file) return;
          remove.mutate(file, {
            onSuccess: () =>
              toast.show({
                tone: "success",
                message: `Removed “${file.name}”`,
              }),
            onError: fail,
          });
        }}
      >
        {removing
          ? `“${removing.name}” is deleted from ${template.name}. Documents already made keep their own copy.`
          : ""}
      </ConfirmDialog>
    </div>
  );
}
