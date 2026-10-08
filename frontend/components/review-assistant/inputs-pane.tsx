'use client';

import { Button } from '@/components/ui/button';
import { FileListItem } from '@/lib/generated-api';
import { Loader2 } from 'lucide-react';
import { DraftSlot } from './draft-slot';
import { FilesSlot } from './files-slot';
import { OutputDefinition, SLOTS, SlotId } from './outputs';
import { InputSelection, selectionProblems } from './selection';

interface InputsPaneProps {
  output: OutputDefinition;
  projectId: string;
  files: FileListItem[];
  currentRevision: number;
  selection: InputSelection;
  readOnly: boolean;
  isStarting: boolean;
  onChange: (selection: InputSelection) => void;
  onGenerate: () => void;
  onRevisionCreated?: () => void;
}

/**
 * The right pane: one section per input the output reads, required first,
 * then Generate. Laid out like the Peer Review memos pane, which holds the
 * same files.
 */
export function InputsPane({
  output,
  projectId,
  files,
  currentRevision,
  selection,
  readOnly,
  isStarting,
  onChange,
  onGenerate,
  onRevisionCreated,
}: InputsPaneProps) {
  const problems = selectionProblems(output, selection);
  const slots: { id: SlotId; optional: boolean }[] = [
    ...output.required.map((id) => ({ id, optional: false })),
    ...output.optional.map((id) => ({ id, optional: true })),
  ];

  return (
    <div className="flex h-full flex-col">
      <div className="bg-background/90 sticky top-0 z-10 flex h-10 shrink-0 items-center border-b px-4 backdrop-blur">
        <span className="text-xs font-medium">Inputs</span>
      </div>

      <div className="min-h-0 flex-1 divide-y overflow-y-auto px-4">
        {slots.map(({ id, optional }) => {
          const slot = SLOTS[id];
          if (slot.kind === 'draft') {
            const draftSlot = id as 'reviewed_draft' | 'revised_draft';
            return (
              <DraftSlot
                key={id}
                slot={slot}
                optional={optional}
                projectId={projectId}
                files={files}
                currentRevision={currentRevision}
                value={selection[draftSlot]}
                disabled={readOnly}
                onChange={(revision) => onChange({ ...selection, [draftSlot]: revision })}
                onRevisionCreated={onRevisionCreated}
              />
            );
          }
          const filesSlot = id as 'reviewer_memos' | 'response_memos';
          return (
            <FilesSlot
              key={id}
              slot={slot}
              optional={optional}
              projectId={projectId}
              files={files}
              currentRevision={currentRevision}
              uploadRevision={selection.reviewed_draft}
              value={selection[filesSlot]}
              disabled={readOnly}
              onChange={(fileIds) => onChange({ ...selection, [filesSlot]: fileIds })}
            />
          );
        })}
      </div>

      {!readOnly && (
        <div className="shrink-0 space-y-2 border-t px-4 py-3">
          <Button className="w-full" disabled={isStarting || problems.length > 0} onClick={onGenerate}>
            {isStarting && <Loader2 className="size-4 animate-spin" />}
            Generate {output.noun}
          </Button>
          {problems.map((problem) => (
            <p key={problem} className="text-[11px] text-muted-foreground">
              {problem}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
