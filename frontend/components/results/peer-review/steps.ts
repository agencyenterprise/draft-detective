import { PeerReviewFacts } from '@/components/results/peer-review/peer-review-derive';
import { WorkflowRunSummary, WorkflowRunStatus } from '@/lib/generated-api';
import { getDisplayStatus } from '@/lib/workflow-state';

export type StepId = 'plan' | 'revise' | 'respond' | 'coverage';

export interface StepDefinition {
  id: StepId;
  title: string;
  /** One line on what this step produces. */
  subtitle: string;
}

/** The sequence, in the order it has to happen. */
export const STEPS: StepDefinition[] = [
  {
    id: 'plan',
    title: 'Plan the revision',
    subtitle: 'Reads the reviewer memos and prepares a document on how to address each point they raise.',
  },
  {
    id: 'revise',
    title: 'Upload your revised draft',
    subtitle:
      'Adds your revised draft as a new revision, so the later steps can compare it against the one the reviewers read.',
  },
  {
    id: 'respond',
    title: 'Respond to the reviewers',
    subtitle:
      'Writes one response memo per reviewer, answering each of their points with what changed and where, or why it did not.',
  },
  {
    id: 'coverage',
    title: 'QA coverage report',
    subtitle:
      'Gives every reviewer point a verdict — addressed, partly, declined, or not — and an overall read for sign-off.',
  },
];

const isComplete = (run?: WorkflowRunSummary) => !!run && getDisplayStatus(run) === WorkflowRunStatus.Completed;

export interface StepState {
  complete: boolean;
  blockedReason: string | null;
  /** The run behind this step, absent for the one the author does by hand. */
  run?: WorkflowRunSummary;
}

/**
 * What each step's marker and status line report. Kept in one function so the
 * rail and the panel cannot disagree about whether a step is done.
 */
export function readStepStates(facts: PeerReviewFacts, planRun?: WorkflowRunSummary): Record<StepId, StepState> {
  return {
    plan: { complete: isComplete(planRun), blockedReason: facts.planBlockedReason, run: planRun },
    revise: { complete: facts.hasRevisedDraft, blockedReason: facts.reviseBlockedReason },
    respond: {
      complete: isComplete(facts.runs.memos),
      blockedReason: facts.comparisonBlockedReason,
      run: facts.runs.memos,
    },
    coverage: {
      complete: isComplete(facts.runs.coverage),
      blockedReason: facts.comparisonBlockedReason,
      run: facts.runs.coverage,
    },
  };
}
