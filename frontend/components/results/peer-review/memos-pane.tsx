'use client';

import { formatFileSize } from '@/components/analysis-form/utils';
import { PeerReviewFacts } from '@/components/results/peer-review/peer-review-derive';
import { useRemoveFileMutation } from '@/components/results/references/mutations';
import { FileTypeIcon } from '@/components/shared/file-type-icon';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { FileDownloadLink } from '@/components/ui/file-download-link';
import { FileListItem } from '@/lib/generated-api';
import { Loader2, Trash2, Upload } from 'lucide-react';
import { ReactNode, useState } from 'react';

interface MemosPaneProps {
  facts: PeerReviewFacts;
  projectId: string;
  readOnly: boolean;
  onUploadMemos: () => void;
  onUploadResponses: () => void;
}

/**
 * The reviewer memos every step reads from. A pane rather than a card above
 * the steps: it is the input to all four of them, so it belongs beside the
 * work rather than scrolling away above it. The author's response memos sit
 * below them in a section of the same shape, since they are the other input
 * the coverage report reads. Worded as the author's, not the viewer's: the
 * person uploading is not always the one who wrote them.
 */
export function MemosPane({ facts, projectId, readOnly, onUploadMemos, onUploadResponses }: MemosPaneProps) {
  const { activeMemos, reviewedRevision, staleMemoRevisions, memos } = facts;
  const { activeResponseMemos, responseMemos, currentRevision, canUploadResponses } = facts;
  const ignoredMemos = memos.filter((memo) => memo.revision !== reviewedRevision);
  const ignoredResponses = responseMemos.filter((memo) => memo.revision !== currentRevision);

  return (
    <div className="flex h-full flex-col">
      <div className="bg-background/90 sticky top-0 z-10 flex h-10 shrink-0 items-center border-b px-4 backdrop-blur">
        <span className="text-xs font-medium">Memos</span>
      </div>

      <div className="min-h-0 flex-1 divide-y overflow-y-auto px-4">
        <MemoSection
          title="Reviewer memos"
          count={activeMemos.length}
          revisionLine={`Revision ${reviewedRevision} · the draft the reviewers read`}
          onAdd={readOnly ? undefined : onUploadMemos}
        >
          <MemoList memos={activeMemos} projectId={projectId} readOnly={readOnly} />
          {ignoredMemos.length > 0 && (
            // `max()` is not "most recently uploaded": memos targeting an older
            // revision than an existing batch are silently ignored by the agent.
            // Unexplained, that behaviour is inexplicable — so say it, and list
            // them here so it can be acted on without leaving the tab.
            <IgnoredMemos
              memos={ignoredMemos}
              projectId={projectId}
              readOnly={readOnly}
              explanation={`${plural(ignoredMemos.length, 'memo')} on revision ${staleMemoRevisions.join(', ')} ${ignoredMemos.length === 1 ? 'is' : 'are'} ignored — the steps read only revision ${reviewedRevision}, the most recent draft that has any. Remove ${ignoredMemos.length === 1 ? 'it' : 'them'}, or upload again targeting revision ${reviewedRevision}.`}
            />
          )}
        </MemoSection>

        <MemoSection
          title="Author responses"
          count={activeResponseMemos.length}
          revisionLine={
            facts.hasRevisedDraft
              ? `Revision ${currentRevision} · the revised draft`
              : 'The revised draft, once uploaded'
          }
          onAdd={readOnly || !canUploadResponses ? undefined : onUploadResponses}
        >
          {activeResponseMemos.length > 0 ? (
            <MemoList memos={activeResponseMemos} projectId={projectId} readOnly={readOnly} noun="response memo" />
          ) : (
            <p className="text-[11.5px] leading-relaxed text-muted-foreground">
              {canUploadResponses
                ? "None yet. Upload the author's final replies to the reviewers and the QA coverage report checks what they say against this revision."
                : "Once the revised draft is uploaded, add the author's final replies to the reviewers here for the QA coverage report to check."}
            </p>
          )}
          {ignoredResponses.length > 0 && (
            <IgnoredMemos
              memos={ignoredResponses}
              projectId={projectId}
              readOnly={readOnly}
              noun="response memo"
              explanation={`${plural(ignoredResponses.length, 'response memo')} from an earlier draft ${ignoredResponses.length === 1 ? 'is' : 'are'} ignored — the coverage report reads only the responses on revision ${currentRevision}, the draft it assesses.`}
            />
          )}
        </MemoSection>
      </div>
    </div>
  );
}

const plural = (count: number, noun: string) => `${count} ${noun}${count === 1 ? '' : 's'}`;

/** One kind of memo: the same header shape for reviewer memos and author responses. */
function MemoSection({
  title,
  count,
  revisionLine,
  onAdd,
  children,
}: {
  title: string;
  count: number;
  /** Which draft this kind of memo is tied to. */
  revisionLine: string;
  /** Omitted when adding is not possible, which hides the button. */
  onAdd?: () => void;
  children: ReactNode;
}) {
  return (
    <section className="space-y-2 py-4">
      <div>
        <div className="flex h-6 items-center gap-2">
          <h3 className="font-mono text-[10px] tracking-wide text-muted-foreground uppercase">{title}</h3>
          <span className="font-mono text-[11px] tabular-nums text-muted-foreground">{count}</span>
          {onAdd && (
            <Button size="xs" variant="outline" className="ml-auto" onClick={onAdd}>
              <Upload className="size-3" />
              Add
            </Button>
          )}
        </div>
        <p className="text-[11px] text-muted-foreground">{revisionLine}</p>
      </div>
      {children}
    </section>
  );
}

function MemoList({
  memos,
  projectId,
  readOnly,
  noun,
  showRevision,
}: {
  memos: FileListItem[];
  projectId: string;
  readOnly: boolean;
  noun?: string;
  showRevision?: boolean;
}) {
  return (
    <ul className="space-y-1.5">
      {memos.map((memo) => (
        <MemoRow
          key={memo.id}
          memo={memo}
          projectId={projectId}
          readOnly={readOnly}
          noun={noun}
          showRevision={showRevision}
        />
      ))}
    </ul>
  );
}

function IgnoredMemos({
  memos,
  projectId,
  readOnly,
  noun,
  explanation,
}: {
  memos: FileListItem[];
  projectId: string;
  readOnly: boolean;
  noun?: string;
  explanation: string;
}) {
  return (
    <div className="pt-2">
      <h4 className="mb-1 font-mono text-[10px] tracking-wide text-amber-700 uppercase dark:text-amber-400">
        Not being read
      </h4>
      <p className="mb-2 text-[11.5px] leading-relaxed text-muted-foreground">{explanation}</p>
      <div className="opacity-70">
        <MemoList memos={memos} projectId={projectId} readOnly={readOnly} noun={noun} showRevision />
      </div>
    </div>
  );
}

function MemoRow({
  memo,
  projectId,
  readOnly,
  noun = 'reviewer memo',
  showRevision = false,
}: {
  memo: FileListItem;
  projectId: string;
  readOnly: boolean;
  /** How the remove button and its confirmation refer to this file. */
  noun?: string;
  /** Ignored memos can span several revisions, so each says which it belongs to. */
  showRevision?: boolean;
}) {
  const [removeOpen, setRemoveOpen] = useState(false);
  const removeFile = useRemoveFileMutation(projectId, memo.id);

  return (
    <li className="flex items-center gap-2 rounded-md border px-2.5 py-2">
      <FileTypeIcon fileType={memo.file_type} className="size-3.5 shrink-0 text-muted-foreground" />
      <FileDownloadLink fileId={memo.id} className="text-primary min-w-0 flex-1 truncate text-[12.5px] hover:underline">
        {memo.file_name || 'Unknown'}
      </FileDownloadLink>
      {showRevision && memo.revision != null && (
        <span className="bg-muted shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
          Rev {memo.revision}
        </span>
      )}
      <span className="shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground">
        {formatFileSize(memo.file_size)}
      </span>

      {!readOnly && (
        <>
          <Button
            size="icon"
            variant="ghost"
            className="size-6 shrink-0"
            disabled={removeFile.isPending}
            onClick={() => setRemoveOpen(true)}
            aria-label={`Remove ${noun}`}
          >
            {removeFile.isPending ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              <Trash2 className="size-3 text-muted-foreground" />
            )}
          </Button>

          <AlertDialog open={removeOpen} onOpenChange={setRemoveOpen}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Remove this {noun}?</AlertDialogTitle>
                <AlertDialogDescription className="break-all">
                  {memo.file_name} will be removed from the project. Steps you run afterwards will no longer read it.
                  Reports already generated are unaffected.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={() => removeFile.mutate()}>Remove</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </>
      )}
    </li>
  );
}
