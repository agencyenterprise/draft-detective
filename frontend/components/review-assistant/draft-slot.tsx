'use client';

import { ReplaceMainDocumentDialog } from '@/components/results/components/replace-main-document-dialog';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { FileListItem } from '@/lib/generated-api';
import { Upload } from 'lucide-react';
import { useState } from 'react';
import { DraftSlotDefinition } from './outputs';
import { revisionDrafts } from './selection';
import { SlotFrame } from './slot-frame';

interface DraftSlotProps {
  slot: DraftSlotDefinition;
  optional: boolean;
  projectId: string;
  files: FileListItem[];
  currentRevision: number;
  value?: number;
  disabled: boolean;
  onChange: (revision: number) => void;
  onRevisionCreated?: () => void;
}

/**
 * A draft is a revision of the main document: pick an existing one, or upload
 * a file, which adds it to the project as the next revision.
 */
export function DraftSlot({
  slot,
  optional,
  projectId,
  files,
  currentRevision,
  value,
  disabled,
  onChange,
  onRevisionCreated,
}: DraftSlotProps) {
  const [uploadOpen, setUploadOpen] = useState(false);
  const drafts = revisionDrafts(files);

  return (
    <SlotFrame
      label={slot.label}
      hint={slot.hint}
      optional={optional}
      action={
        !disabled && (
          <Button size="xs" variant="outline" onClick={() => setUploadOpen(true)}>
            <Upload className="size-3" />
            Upload
          </Button>
        )
      }
    >
      <Select
        value={value === undefined ? '' : String(value)}
        onValueChange={(v) => onChange(Number(v))}
        disabled={disabled || drafts.length === 0}
      >
        <SelectTrigger className="h-8 w-full text-[12.5px]" aria-label={slot.label}>
          <SelectValue placeholder="Choose a revision" />
        </SelectTrigger>
        <SelectContent>
          {drafts.map(({ revision, file }) => (
            <SelectItem key={file.id} value={String(revision)} className="text-[12.5px]">
              <span className="font-medium">Rev {revision}</span>{' '}
              <span className="text-muted-foreground">
                {revision === currentRevision ? '· current · ' : '· '}
                {file.file_name}
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <ReplaceMainDocumentDialog
        isOpen={uploadOpen}
        projectId={projectId}
        hideRerunOption
        onClose={() => setUploadOpen(false)}
        onRevisionCreated={() => {
          // The upload becomes the next revision; pick it for this input.
          onChange(currentRevision + 1);
          onRevisionCreated?.();
        }}
      />
    </SlotFrame>
  );
}
