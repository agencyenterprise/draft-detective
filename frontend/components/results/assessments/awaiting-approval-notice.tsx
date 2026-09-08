'use client';

import { HelpLink } from '@/components/help/help-link';
import { UnmatchedReferencesApproveDialog } from '@/components/results/references/unmatched-references-approve-dialog';
import { useReferenceApprovalFlow } from '@/components/results/references/use-reference-approval-flow';
import { Button } from '@/components/ui/button';
import { requiresGate } from '@/components/workflows/utils';
import { ProjectDetailed, WorkflowGate, WorkflowRunDetail } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { ArrowRight, BookOpen, Loader2, UserCheck } from 'lucide-react';

interface AwaitingApprovalNoticeProps {
  projectDetail: ProjectDetailed;
  workflowRun: WorkflowRunDetail;
  readOnly: boolean;
  onNavigateToReferences: () => void;
}

/**
 * What the assessments pane shows in place of results while a run is waiting
 * on the user. A run in this state has produced nothing yet, and the reason it
 * hasn't started is not visible anywhere else on this tab, so the pane names
 * the gate, says what clears it, and offers the two ways to clear it.
 */
export function AwaitingApprovalNotice({
  projectDetail,
  workflowRun,
  readOnly,
  onNavigateToReferences,
}: AwaitingApprovalNoticeProps) {
  const { getWorkflowTypeName, workflowTypes } = useWorkflowTypes();
  const name = getWorkflowTypeName(workflowRun.run.type);

  if (requiresGate(workflowRun.run.type, WorkflowGate.ReferenceReview, workflowTypes)) {
    return (
      <ReferenceReviewNotice
        projectDetail={projectDetail}
        assessmentName={name}
        readOnly={readOnly}
        onNavigateToReferences={onNavigateToReferences}
      />
    );
  }

  // No other gate exists yet. If one is added without a notice of its own,
  // this still tells the reader the run is waiting on them rather than stuck.
  return (
    <Notice title={`${name} is waiting for your approval.`}>
      <p>It has not started yet and will run as soon as you approve it.</p>
    </Notice>
  );
}

function ReferenceReviewNotice({
  projectDetail,
  assessmentName,
  readOnly,
  onNavigateToReferences,
}: {
  projectDetail: ProjectDetailed;
  assessmentName: string;
  readOnly: boolean;
  onNavigateToReferences: () => void;
}) {
  const approval = useReferenceApprovalFlow(projectDetail, projectDetail.project.id);
  const { unmatchedCount } = approval;

  return (
    <Notice title={`${assessmentName} is waiting for your reference review.`}>
      <p>
        It reads each citation against the source it cites, so it needs those sources before it can start. Check that
        every reference is matched to the right file, upload or fetch any that are missing, then approve to start the
        analysis.{' '}
        <HelpLink topic="source-files" onReviewReferences={onNavigateToReferences}>
          Why this is needed
        </HelpLink>
      </p>

      <p className={unmatchedCount > 0 ? 'text-amber-800 dark:text-amber-300' : 'text-muted-foreground'}>
        {unmatchedCount > 0 ? (
          <>
            <strong className="font-medium">
              {unmatchedCount} reference{unmatchedCount === 1 ? ' has' : 's have'} no source file yet.
            </strong>{' '}
            You can still approve; claims citing {unmatchedCount === 1 ? 'it' : 'them'} will be reported as
            unverifiable.
          </>
        ) : (
          'Every reference has its source file. Ready when you are.'
        )}
      </p>

      {!readOnly && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button size="sm" variant="outline" onClick={onNavigateToReferences}>
            <BookOpen className="size-3.5" />
            Review references
            <ArrowRight className="size-3" />
          </Button>
          <Button size="sm" onClick={approval.handleApprove} disabled={approval.isApproveDisabled}>
            {approval.showApproveButtonSpinner && <Loader2 className="size-3.5 animate-spin" aria-hidden />}
            {approval.approveButtonText}
          </Button>
        </div>
      )}

      <UnmatchedReferencesApproveDialog
        open={approval.showUnmatchedWarning}
        onOpenChange={approval.setShowUnmatchedWarning}
        unmatchedCount={unmatchedCount}
        onConfirmApprove={approval.handleConfirmApprove}
      />
    </Notice>
  );
}

/** The amber frame the reference-review banner uses, sized for the pane. */
function Notice({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
      <div className="flex items-start gap-3">
        <UserCheck className="mt-0.5 size-4 shrink-0 text-amber-700 dark:text-amber-400" aria-hidden />
        <div className="min-w-0 space-y-2 text-sm leading-relaxed">
          <p className="font-medium">{title}</p>
          {children}
        </div>
      </div>
    </div>
  );
}
