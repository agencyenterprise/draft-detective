'use client';

import { GROUP, fileGroup, sortFiles } from '@/components/results/files/role';
import { FileTypeIcon } from '@/components/shared/file-type-icon';
import { FileUploadDialog } from '@/components/results/references/file-upload-dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { FileListItem, FileRole, listProjectFilesEndpointApiProjectProjectIdFilesGet } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { Upload } from 'lucide-react';
import { useState } from 'react';
import { FilesSlotDefinition } from './outputs';
import { SlotFrame } from './slot-frame';

interface FilesSlotProps {
  slot: FilesSlotDefinition;
  optional: boolean;
  projectId: string;
  files: FileListItem[];
  currentRevision: number;
  /** Revision a reviewer memo upload attaches to: the reviewed draft when one is picked. */
  uploadRevision?: number;
  value: string[];
  disabled: boolean;
  onChange: (fileIds: string[]) => void;
}

/**
 * One or more project files. Files stored with the slot's role are listed
 * first; any other project document can be picked too, since a memo uploaded
 * under the wrong role is still that memo. Uploads are stored with the slot's
 * role and picked once they complete.
 */
export function FilesSlot({
  slot,
  optional,
  projectId,
  files,
  currentRevision,
  uploadRevision,
  value,
  disabled,
  onChange,
}: FilesSlotProps) {
  const [showAll, setShowAll] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  // IDs already in the project when the upload dialog opened: whatever has
  // the slot's role beyond them once the upload completes is the upload.
  const [uploadBaseline, setUploadBaseline] = useState<Set<string>>(new Set());

  const pickUploaded = async () => {
    try {
      const projectFiles = await listProjectFilesEndpointApiProjectProjectIdFilesGet({
        path: { project_id: projectId },
      });
      const uploaded = projectFiles
        .filter((f) => f.role === slot.uploadRole && !uploadBaseline.has(f.id))
        .map((f) => f.id);
      onChange([...new Set([...value, ...uploaded])]);
    } catch {
      // The files are uploaded either way; they can be ticked by hand.
    }
  };

  const sameRole = sortFiles(files.filter((f) => f.role === slot.uploadRole));
  const others = sortFiles(files.filter((f) => f.role !== slot.uploadRole));
  // Picked files stay visible even when they come from the "all files" list.
  const listed = showAll ? [...sameRole, ...others] : [...sameRole, ...others.filter((f) => value.includes(f.id))];

  const toggle = (fileId: string, checked: boolean) =>
    onChange(checked ? [...value, fileId] : value.filter((id) => id !== fileId));

  return (
    <SlotFrame
      label={slot.label}
      hint={slot.hint}
      optional={optional}
      action={
        !disabled && (
          <Button
            size="xs"
            variant="outline"
            onClick={() => {
              setUploadBaseline(new Set(files.map((f) => f.id)));
              setUploadOpen(true);
            }}
          >
            <Upload className="size-3" />
            Upload
          </Button>
        )
      }
    >
      {listed.length === 0 ? (
        <p className="text-[11.5px] leading-relaxed text-muted-foreground">
          No {slot.label.toLowerCase()} in this project yet. Upload them, or pick from all project files.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {listed.map((file) => (
            <FileOption
              key={file.id}
              file={file}
              showRole={file.role !== slot.uploadRole}
              checked={value.includes(file.id)}
              disabled={disabled}
              onCheckedChange={(checked) => toggle(file.id, checked)}
            />
          ))}
        </ul>
      )}
      {others.length > 0 && (
        <Button variant="ghost" size="xs" className="-ml-2 text-muted-foreground" onClick={() => setShowAll((v) => !v)}>
          {showAll ? `Show only ${slot.label.toLowerCase()}` : `Pick from all project files (${files.length})`}
        </Button>
      )}

      <FileUploadDialog
        isOpen={uploadOpen}
        projectId={projectId}
        title={`Upload ${slot.label.toLowerCase()}`}
        description={slot.hint}
        multiple
        fileRole={slot.uploadRole}
        targetRevision={slot.uploadRole === FileRole.ReviewerMemo ? uploadRevision : undefined}
        currentRevision={currentRevision}
        onComplete={pickUploaded}
        onCancel={() => setUploadOpen(false)}
      />
    </SlotFrame>
  );
}

interface FileOptionProps {
  file: FileListItem;
  /** Files from outside the slot's own role say what they are. */
  showRole: boolean;
  checked: boolean;
  disabled: boolean;
  onCheckedChange: (checked: boolean) => void;
}

/** A row shaped like the memos pane's, with a checkbox in place of the remove button. */
function FileOption({ file, showRole, checked, disabled, onCheckedChange }: FileOptionProps) {
  const group = GROUP[fileGroup(file.role)];
  const inputId = `pick-${file.id}`;
  return (
    <li>
      <label
        htmlFor={inputId}
        className={cn(
          'flex cursor-pointer items-center gap-2 rounded-md border px-2.5 py-2 transition-colors',
          checked ? 'border-primary/40 bg-primary/5' : 'hover:bg-accent/40',
        )}
      >
        <Checkbox
          id={inputId}
          checked={checked}
          disabled={disabled}
          onCheckedChange={(c) => onCheckedChange(c === true)}
        />
        <FileTypeIcon fileType={file.file_type} className="size-3.5 shrink-0 text-muted-foreground" />
        <span className="min-w-0 flex-1 truncate text-[12.5px]">{file.file_name || 'Unknown'}</span>
        {showRole && (
          <span className={cn('shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium', group.className)}>
            {group.label}
          </span>
        )}
        {file.revision != null && (
          <span className="bg-muted shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
            Rev {file.revision}
          </span>
        )}
      </label>
    </li>
  );
}
