/**
 * What the user has picked for each input, and how that becomes a request.
 * Pure and React-free so the rules can be tested and read next to the backend's
 * `resolve_input_files` (lib/services/review_assistant_runs.py).
 */

import { FileListItem, FileRole, ReviewAssistantInputs } from '@/lib/generated-api';
import { OutputDefinition, SLOTS, SlotId } from './outputs';

/** Drafts are picked by revision number, memo slots by file ID. */
export interface InputSelection {
  reviewed_draft?: number;
  revised_draft?: number;
  reviewer_memos: string[];
  response_memos: string[];
}

export const EMPTY_SELECTION: InputSelection = { reviewer_memos: [], response_memos: [] };

/** Each revision's main document, newest first. */
export function revisionDrafts(files: FileListItem[]): { revision: number; file: FileListItem }[] {
  return files
    .filter((f): f is FileListItem & { revision: number } => f.role === FileRole.Main && f.revision != null)
    .map((file) => ({ revision: file.revision, file }))
    .sort((a, b) => b.revision - a.revision);
}

/**
 * A starting point that matches what the Peer Review tab would read: the
 * latest revision with reviewer memos is the reviewed draft and its memos are
 * picked, the current revision is the revised draft when it is a different
 * one, and its author responses are picked. The user changes any of it.
 */
export function defaultSelection(
  output: OutputDefinition,
  files: FileListItem[],
  currentRevision: number,
): InputSelection {
  const slots = new Set<SlotId>([...output.required, ...output.optional]);
  const memos = files.filter((f) => f.role === FileRole.ReviewerMemo && f.revision != null);
  const memoRevisions = memos.map((f) => f.revision as number);
  const reviewedRevision = memoRevisions.length > 0 ? Math.max(...memoRevisions) : currentRevision;
  const hasRevisedDraft = reviewedRevision !== currentRevision;

  return {
    reviewed_draft: reviewedRevision,
    revised_draft: slots.has('revised_draft') && hasRevisedDraft ? currentRevision : undefined,
    reviewer_memos: memos.filter((f) => f.revision === reviewedRevision).map((f) => f.id),
    response_memos:
      slots.has('response_memos') && hasRevisedDraft
        ? files.filter((f) => f.role === FileRole.ResponseMemo && f.revision === currentRevision).map((f) => f.id)
        : [],
  };
}

function isFilled(selection: InputSelection, slot: SlotId): boolean {
  const value = selection[slot];
  return Array.isArray(value) ? value.length > 0 : value !== undefined;
}

/** Why the output cannot run on this selection yet, or an empty list. */
export function selectionProblems(output: OutputDefinition, selection: InputSelection): string[] {
  const problems = output.required
    .filter((slot) => !isFilled(selection, slot))
    .map((slot) => `Choose the ${SLOTS[slot].label.toLowerCase()}.`);
  if (
    output.required.includes('revised_draft') &&
    selection.reviewed_draft !== undefined &&
    selection.reviewed_draft === selection.revised_draft
  ) {
    problems.push('The reviewed and revised drafts must be different revisions.');
  }
  return problems;
}

/** The request body's inputs: draft revisions become their main file IDs. */
export function toRequestInputs(
  output: OutputDefinition,
  selection: InputSelection,
  files: FileListItem[],
): ReviewAssistantInputs {
  const slots = new Set<SlotId>([...output.required, ...output.optional]);
  const mainOf = (revision?: number) =>
    revision === undefined ? null : (revisionDrafts(files).find((d) => d.revision === revision)?.file.id ?? null);
  return {
    reviewed_draft: slots.has('reviewed_draft') ? mainOf(selection.reviewed_draft) : null,
    revised_draft: slots.has('revised_draft') ? mainOf(selection.revised_draft) : null,
    reviewer_memos: slots.has('reviewer_memos') ? selection.reviewer_memos : [],
    response_memos: slots.has('response_memos') ? selection.response_memos : [],
  };
}
