import { FileListItem, ReviewAssistantRun } from '@/lib/generated-api';
import { SLOTS, SlotId } from './outputs';

/** Backend slot folder names (lib/workflows/review_assistant/inputs.py), in display order. */
const FOLDER_BY_SLOT: Record<SlotId, string> = {
  reviewed_draft: 'reviewed-draft',
  reviewer_memos: 'reviewer-memos',
  revised_draft: 'revised-draft',
  response_memos: 'response-memos',
};

/** "Reviewed draft: rev 1 · 3 reviewer memos", from the files the run was handed. */
export function describeInputs(run: ReviewAssistantRun, files: FileListItem[]): string[] {
  const byId = new Map(files.map((f) => [f.id, f]));
  return (Object.keys(FOLDER_BY_SLOT) as SlotId[]).flatMap((slotId) => {
    const ids = run.input_files[FOLDER_BY_SLOT[slotId]];
    if (!ids?.length) return [];
    const slot = SLOTS[slotId];
    if (slot.kind === 'draft') {
      const file = byId.get(ids[0]);
      return [file ? `${slot.label}: rev ${file.revision}` : `${slot.label}: a deleted file`];
    }
    const noun = slot.label.toLowerCase();
    return [ids.length === 1 ? `1 ${noun.replace(/s$/, '')}` : `${ids.length} ${noun}`];
  });
}
