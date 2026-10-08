import { FileRole, WorkflowRunType } from '@/lib/generated-api';

/** One input of an output; the names match the backend request fields. */
export type SlotId = 'reviewed_draft' | 'revised_draft' | 'reviewer_memos' | 'response_memos';

interface SlotBase {
  id: SlotId;
  label: string;
  hint: string;
}

/** One revision of the main document. */
export interface DraftSlotDefinition extends SlotBase {
  kind: 'draft';
}

/** One or more project files. */
export interface FilesSlotDefinition extends SlotBase {
  kind: 'files';
  /** The role a file uploaded into this slot is stored with. */
  uploadRole: FileRole;
}

export type SlotDefinition = DraftSlotDefinition | FilesSlotDefinition;

export const SLOTS: Record<SlotId, SlotDefinition> = {
  reviewed_draft: {
    id: 'reviewed_draft',
    label: 'Reviewed draft',
    hint: 'The version the reviewers read.',
    kind: 'draft',
  },
  revised_draft: {
    id: 'revised_draft',
    label: 'Revised draft',
    hint: "The version that addresses the reviewers' points.",
    kind: 'draft',
  },
  reviewer_memos: {
    id: 'reviewer_memos',
    label: 'Reviewer memos',
    hint: 'The memos the reviewers returned.',
    kind: 'files',
    uploadRole: FileRole.ReviewerMemo,
  },
  response_memos: {
    id: 'response_memos',
    label: 'Author responses',
    hint: 'The final reply to each reviewer. The report quotes them and checks each claimed change against the revised draft.',
    kind: 'files',
    uploadRole: FileRole.ResponseMemo,
  },
};

/** The three outputs, keyed by the workflow that produces them. */
export type ReviewOutputType =
  | typeof WorkflowRunType.RevisionPlanningSummary
  | typeof WorkflowRunType.ReviewerResponseMemos
  | typeof WorkflowRunType.ReviewerCoverageReport;

export interface OutputDefinition {
  type: ReviewOutputType;
  title: string;
  /** The title mid-sentence ("Generate the …"), keeping acronyms. */
  noun: string;
  summary: string;
  required: SlotId[];
  optional: SlotId[];
}

/** Mirrors REVIEW_OUTPUT_SPECS in lib/workflows/review_assistant/inputs.py. */
export const OUTPUTS: OutputDefinition[] = [
  {
    type: WorkflowRunType.RevisionPlanningSummary,
    title: 'Revision plan',
    noun: 'revision plan',
    summary: 'Every reviewer point, where it lands in the draft, and a suggestion for addressing it.',
    required: ['reviewed_draft', 'reviewer_memos'],
    optional: [],
  },
  {
    type: WorkflowRunType.ReviewerResponseMemos,
    title: 'Response memos',
    noun: 'response memos',
    summary: 'One reply per reviewer, answering each point with what changed and where, or why it did not.',
    required: ['reviewed_draft', 'reviewer_memos', 'revised_draft'],
    optional: [],
  },
  {
    type: WorkflowRunType.ReviewerCoverageReport,
    title: 'QA coverage report',
    noun: 'QA coverage report',
    summary: 'A verdict on every reviewer point and an overall read on the revision, for sign-off.',
    required: ['reviewed_draft', 'reviewer_memos', 'revised_draft'],
    optional: ['response_memos'],
  },
];

export function outputDefinition(type: ReviewOutputType): OutputDefinition {
  const output = OUTPUTS.find((o) => o.type === type);
  if (!output) throw new Error(`Unknown review output ${type}`);
  return output;
}
