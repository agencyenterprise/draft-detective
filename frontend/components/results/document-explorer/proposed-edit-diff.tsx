'use client';

import { cn } from '@/lib/utils';
import { diffWords } from 'diff';
import { PencilLineIcon } from 'lucide-react';
import { useMemo } from 'react';
import { formatLineLabel } from './issue-lines';
import { isDeletion, type ProposedEdit } from './proposed-edit';

export type DiffTokenKind = 'same' | 'removed' | 'added';

export interface DiffToken {
  kind: DiffTokenKind;
  value: string;
}

/**
 * The quote and its replacement as one run of word-level tokens.
 *
 * `diffWords` rather than `diffWordsWithSpace`: whitespace-only differences are
 * not changes a reader cares about, and treating them as such broke every
 * altered word into three tokens — the word, the space before it, the space
 * after — which read as noise.
 */
export function diffTokens(original: string, replacement: string): DiffToken[] {
  return diffWords(original, replacement).map((part) => ({
    kind: part.added ? 'added' : part.removed ? 'removed' : 'same',
    value: part.value,
  }));
}

const TOKEN_CLASSES: Record<DiffTokenKind, string | undefined> = {
  same: undefined,
  removed:
    'rounded-[2px] bg-red-100/70 text-red-700 line-through decoration-red-500/70 dark:bg-red-950/40 dark:text-red-300',
  added: 'rounded-[2px] bg-green-100/70 text-green-700 dark:bg-green-950/40 dark:text-green-300',
};

/**
 * The quote as it stands beside the quote as proposed.
 *
 * Rendered as plain text, never through Markdown: the quote is taken verbatim
 * from the document source, so its asterisks and brackets are part of what the
 * edit touches and have to stay visible. Rendering them would also let a link
 * or a heading escape into the note's layout.
 */
function EditText({ edit }: { edit: ProposedEdit }) {
  const tokens = useMemo(() => diffTokens(edit.original_text, edit.replacement_text), [edit]);

  if (isDeletion(edit)) {
    return (
      <p className="text-[12px] leading-relaxed break-words whitespace-pre-wrap">
        <span className={TOKEN_CLASSES.removed}>{edit.original_text}</span>
      </p>
    );
  }

  return (
    <p className="text-[12px] leading-relaxed break-words whitespace-pre-wrap">
      {tokens.map((token, index) => (
        // Tokens have no identity of their own, and the run is regenerated
        // whole whenever the edit changes, so the position is the key.
        <span key={`${index}-${token.kind}`} className={TOKEN_CLASSES[token.kind]}>
          {token.value}
        </span>
      ))}
    </p>
  );
}

/**
 * One edit: what it does to the text, and why.
 *
 * The line label sits in the card only when the list has several edits, each
 * on its own line; a single edit shows its line in the block header instead.
 */
function ProposedEditCard({ edit, showLine }: { edit: ProposedEdit; showLine: boolean }) {
  const deletion = isDeletion(edit);
  return (
    <li aria-label="Proposed edit" className="border-t border-dashed pt-1.5 first:border-t-0 first:pt-0">
      {(deletion || showLine) && (
        <div className="mb-0.5 flex items-baseline gap-1.5">
          {deletion && (
            <span className="font-mono text-[9.5px] tracking-wide text-red-700 uppercase dark:text-red-300">
              Delete
            </span>
          )}
          {showLine && (
            <span className="ml-auto shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground">
              {formatLineLabel(edit.start_line, edit.end_line)}
            </span>
          )}
        </div>
      )}
      <EditText edit={edit} />
      <p className="mt-1 text-[11px] leading-snug text-muted-foreground">{edit.rationale}</p>
    </li>
  );
}

/**
 * Every edit an issue proposes, below its suggested action. Styled as the
 * suggested-action block is, since it is the same kind of thing: what to do
 * about the finding, only stated as the exact words rather than as advice.
 */
export function ProposedEdits({ edits, className }: { edits: ProposedEdit[]; className?: string }) {
  if (edits.length === 0) return null;

  const single = edits.length === 1 ? edits[0] : null;

  return (
    <div className={cn('bg-background/60 rounded border border-dashed px-2 py-1.5', className)}>
      <p className="mb-1 flex items-center gap-1 font-mono text-[9.5px] tracking-wide text-muted-foreground uppercase">
        <PencilLineIcon className="size-3" />
        {single ? 'Proposed edit' : `Proposed edits (${edits.length})`}
        {single && (
          <span className="ml-auto shrink-0 text-[10px] tabular-nums normal-case">
            {formatLineLabel(single.start_line, single.end_line)}
          </span>
        )}
      </p>
      <ul className="space-y-1.5">
        {edits.map((edit) => (
          <ProposedEditCard key={edit.id} edit={edit} showLine={single === null} />
        ))}
      </ul>
    </div>
  );
}
