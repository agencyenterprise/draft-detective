'use client';

import { ReplaceMainDocumentDialog } from '@/components/results/components/replace-main-document-dialog';
import { PeerReviewStageAction } from '@/components/results/peer-review/peer-review-stage-action';
import { usePeerReviewState } from '@/components/results/peer-review/use-peer-review-state';
import { FileUploadDialog } from '@/components/results/references/file-upload-dialog';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { SimpleDeepAgentResults } from '@/components/workflows/results/simple-deep-agent-results';
import { FileRole, ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { WIDE_ENOUGH_FOR_PANE, useMediaQuery } from '@/lib/use-media-query';
import { ClipboardCheck, History, ListChecks, Lock, MessagesSquare, Upload } from 'lucide-react';
import { ReactNode, useState } from 'react';
import { Rail, RailToggle, SidePane, useRailState } from '../panes';
import { MemosPane } from './memos-pane';
import { StepRail } from './step-rail';
import { STEPS, StepId, readStepStates } from './steps';

interface PeerReviewTabProps {
  projectDetail: ProjectDetailed;
  readOnly: boolean;
  onRevisionChange?: (revision: number) => void;
  onRevisionCreated?: () => void;
  onNavigateToDocumentExplorer: (lineRange?: [number, number]) => void;
}

/**
 * Peer review. The rail is a stepper rather than a filter, the
 * pane holds one step at a time, and the memos every step reads from sit in
 * the right pane — where they stay in view instead of scrolling away above the
 * work, as the card above the steps used to.
 */
export function PeerReviewTab({
  projectDetail,
  readOnly,
  onRevisionChange,
  onRevisionCreated,
  onNavigateToDocumentExplorer,
}: PeerReviewTabProps) {
  const projectId = projectDetail.project.id;
  const { facts, planFallback, startStage, cancelRun, isStarting } = usePeerReviewState({ projectDetail });
  const { runs, currentRevision, reviewedRevision, hasRevisedDraft, isViewingOldRevision } = facts;

  const rail = useRailState();
  const isWideEnoughForMemos = useMediaQuery(WIDE_ENOUGH_FOR_PANE);
  const [memosOpen, setMemosOpen] = useState(false);
  const [memoUploadOpen, setMemoUploadOpen] = useState(false);
  const [revisionDialogOpen, setRevisionDialogOpen] = useState(false);

  // The plan for the reviewed draft stays relevant once a newer revision
  // exists, so fall back to the run on that revision rather than showing an
  // empty first step.
  const planRun = runs.plan ?? planFallback?.run;
  const planRunRevision = runs.plan ? facts.viewedRevision : planFallback?.revision;
  const planRunProject = runs.plan ? projectDetail : (planFallback?.projectDetail ?? projectDetail);
  const states = readStepStates(facts, planRun);

  // Land on the furthest step with something to show. Held in state rather than
  // recomputed, so the project poll cannot move the selection out from under
  // someone who is reading.
  const [activeStep, setActiveStep] = useState<StepId>(() => {
    if (runs.coverage) return 'coverage';
    if (runs.memos || hasRevisedDraft) return 'respond';
    if (states.plan.complete) return 'revise';
    return 'plan';
  });

  const stepIndex = STEPS.findIndex((step) => step.id === activeStep);
  const step = STEPS[stepIndex];
  const state = states[activeStep];

  const memoDialog = (
    <FileUploadDialog
      isOpen={memoUploadOpen}
      projectId={projectId}
      title="Upload reviewer memos"
      description="Add the memos your peer reviewers returned. They are read against the draft the reviewers saw."
      multiple
      fileRole={FileRole.ReviewerMemo}
      allowRevisionSelection
      currentRevision={currentRevision}
      onCancel={() => setMemoUploadOpen(false)}
      onComplete={() => setMemoUploadOpen(false)}
    />
  );

  if (reviewedRevision === null) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="max-w-md space-y-3 text-center">
          <MessagesSquare className="mx-auto size-7 text-muted-foreground" />
          <p className="text-sm font-medium">No reviewer memos yet</p>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Once your draft comes back from peer review, upload the reviewers&apos; memos here. Draft Detective turns
            their points into a revision plan, then — after you upload your revised draft — drafts a response memo per
            reviewer and a coverage report for a QA manager.
          </p>
          {!readOnly && (
            <Button size="sm" className="mt-1" onClick={() => setMemoUploadOpen(true)}>
              <Upload className="size-3.5" />
              Upload reviewer memos
            </Button>
          )}
        </div>
        {memoDialog}
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0">
      {memoDialog}
      <ReplaceMainDocumentDialog
        isOpen={revisionDialogOpen}
        projectId={projectId}
        onClose={() => setRevisionDialogOpen(false)}
        onRevisionCreated={onRevisionCreated}
        hideRerunOption
      />

      <Rail state={rail} label="Steps">
        <StepRail
          states={states}
          activeStep={activeStep}
          onSelectStep={(step) => {
            setActiveStep(step);
            rail.close();
          }}
        />
      </Rail>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-10 shrink-0 items-center gap-2 border-b px-2">
          <RailToggle state={rail} label="Steps" />

          <span className="min-w-0 truncate text-xs text-muted-foreground">
            Step {stepIndex + 1} of {STEPS.length}
          </span>

          <span className="ml-auto flex shrink-0 items-center gap-1.5">
            {isViewingOldRevision && onRevisionChange && (
              <>
                <span className="text-xs text-muted-foreground">
                  Viewing revision {facts.viewedRevision}; the steps run on revision {currentRevision}
                </span>
                <Button size="xs" variant="outline" onClick={() => onRevisionChange(currentRevision)}>
                  <History className="size-3" />
                  View current
                </Button>
              </>
            )}
            {!readOnly && !state.blockedReason && <ToolbarAction />}

            {!isWideEnoughForMemos && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="xs" variant="outline" onClick={() => setMemosOpen(true)}>
                    <MessagesSquare className="size-3" />
                    Memos
                    <span className="font-mono tabular-nums">{facts.activeMemos.length}</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>The reviewer memos every step reads from</TooltipContent>
              </Tooltip>
            )}
          </span>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-4xl px-6 py-5">
            <header className="border-b pb-4">
              <h1 className="text-base font-semibold tracking-tight">{step.title}</h1>
              <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{step.subtitle}</p>
            </header>

            <div className="pt-4">
              {state.blockedReason ? (
                <Blocked reason={state.blockedReason} />
              ) : activeStep === 'plan' ? (
                <PlanStep />
              ) : activeStep === 'revise' ? (
                <ReviseStep />
              ) : activeStep === 'respond' ? (
                <RespondStep />
              ) : (
                <CoverageStep />
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Always a column where there is room; a sheet the reader opens where
          there is not, since the memos are context rather than a selection. */}
      <SidePane
        open={isWideEnoughForMemos || memosOpen}
        onClose={() => setMemosOpen(false)}
        label="Reviewer memos"
        className="w-[22rem] xl:w-[24rem]"
      >
        <MemosPane
          facts={facts}
          projectId={projectId}
          readOnly={readOnly}
          onUploadMemos={() => setMemoUploadOpen(true)}
        />
      </SidePane>
    </div>
  );

  /**
   * The current step's action. Only for steps that already produced something:
   * a step with nothing yet carries its button in the call to action, where it
   * sits under the description explaining what it will do.
   */
  function ToolbarAction() {
    if (activeStep === 'plan' && planRun) {
      return (
        <PeerReviewStageAction
          label="Generate planning summary"
          reRunLabel={planFallback ? `Generate again for revision ${currentRevision}` : undefined}
          run={planRun}
          disabled={false}
          isStarting={isStarting}
          size="xs"
          onStart={() => startStage([WorkflowRunType.RevisionPlanningSummary])}
          onCancel={cancelRun}
        />
      );
    }
    if (activeStep === 'revise' && hasRevisedDraft) {
      return (
        <Button variant="outline" size="xs" onClick={() => setRevisionDialogOpen(true)}>
          <Upload className="size-3" />
          Create another revision
        </Button>
      );
    }
    if (activeStep === 'respond' && runs.memos) {
      return (
        <PeerReviewStageAction
          label="Generate response memos"
          run={runs.memos}
          disabled={false}
          isStarting={isStarting}
          size="xs"
          onStart={() => startStage([WorkflowRunType.ReviewerResponseMemos])}
          onCancel={cancelRun}
        />
      );
    }
    if (activeStep === 'coverage' && runs.coverage) {
      return (
        <PeerReviewStageAction
          label="Generate coverage report"
          run={runs.coverage}
          disabled={false}
          isStarting={isStarting}
          size="xs"
          onStart={() => startStage([WorkflowRunType.ReviewerCoverageReport])}
          onCancel={cancelRun}
        />
      );
    }
    return null;
  }

  function PlanStep() {
    if (!planRun) {
      return (
        <StepCta
          icon={ListChecks}
          title="Turn the reviewers' memos into a revision plan"
          description={`Reads the ${facts.activeMemos.length} memo${facts.activeMemos.length === 1 ? '' : 's'} on revision ${reviewedRevision} against that revision's draft, reproduces each memo verbatim, and adds a planning note under every point.`}
          action={
            !readOnly && (
              <PeerReviewStageAction
                label="Generate planning summary"
                disabled={false}
                isStarting={isStarting}
                size="default"
                onStart={() => startStage([WorkflowRunType.RevisionPlanningSummary])}
                onCancel={cancelRun}
              />
            )
          }
        />
      );
    }

    return (
      <div className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Based on revision {planRunRevision} — the draft your reviewers read, and the {facts.activeMemos.length} memo
          {facts.activeMemos.length === 1 ? '' : 's'} attached to it.
          {planFallback && ' It still applies: those memos have not changed.'}
        </p>
        <SimpleDeepAgentResults
          project={planRunProject}
          workflowDetail={planRun}
          workflowName="Revision-Planning Summary"
          onNavigateToDocumentExplorer={onNavigateToDocumentExplorer}
        />
      </div>
    );
  }

  function ReviseStep() {
    if (!hasRevisedDraft) {
      return (
        <StepCta
          icon={Upload}
          title="Upload the draft you revised"
          description={`Revision ${reviewedRevision} is the draft your reviewers read. Uploading your revised version creates a new revision — revision ${reviewedRevision} and all its results are kept, and steps 3 and 4 compare the two.`}
          action={
            !readOnly && (
              <Button onClick={() => setRevisionDialogOpen(true)}>
                <Upload className="size-4" />
                Upload revised draft
              </Button>
            )
          }
        />
      );
    }

    return (
      <p className="text-[13px] leading-relaxed text-muted-foreground">
        Revision {currentRevision} is your revised draft. Revision {reviewedRevision} is kept as the draft the reviewers
        read, and steps 3 and 4 compare the two.
      </p>
    );
  }

  function RespondStep() {
    if (!runs.memos) {
      return (
        <StepCta
          icon={MessagesSquare}
          title="Draft a reply to every reviewer point"
          description={`One response memo per reviewer. Compares revision ${currentRevision} against revision ${reviewedRevision} to state, for every point, what changed and where, or why it was not changed.`}
          action={
            !readOnly && (
              <PeerReviewStageAction
                label="Generate response memos"
                disabled={false}
                isStarting={isStarting}
                size="default"
                onStart={() => startStage([WorkflowRunType.ReviewerResponseMemos])}
                onCancel={cancelRun}
              />
            )
          }
        />
      );
    }

    return (
      <div className="space-y-3">
        <SimpleDeepAgentResults
          project={projectDetail}
          workflowDetail={runs.memos}
          workflowName="Reviewer Response Memos"
          onNavigateToDocumentExplorer={onNavigateToDocumentExplorer}
        />
      </div>
    );
  }

  function CoverageStep() {
    if (!runs.coverage) {
      return (
        <StepCta
          icon={ClipboardCheck}
          title="Sign off on how responsive the revision was"
          description="A single view for a QA manager: every reviewer point with a verdict (addressed, partially addressed, declined with rationale, or not addressed), a summary count table, and an overall responsiveness read."
          action={
            !readOnly && (
              <PeerReviewStageAction
                label="Generate coverage report"
                disabled={false}
                isStarting={isStarting}
                size="default"
                onStart={() => startStage([WorkflowRunType.ReviewerCoverageReport])}
                onCancel={cancelRun}
              />
            )
          }
        />
      );
    }

    return (
      <div className="space-y-3">
        <SimpleDeepAgentResults
          project={projectDetail}
          workflowDetail={runs.coverage}
          workflowName="Reviewer Coverage Report"
          onNavigateToDocumentExplorer={onNavigateToDocumentExplorer}
        />
      </div>
    );
  }
}

function Blocked({ reason }: { reason: string }) {
  return (
    <div className="rounded-md border border-dashed px-4 py-8 text-center">
      <Lock className="mx-auto size-4 text-muted-foreground" />
      <p className="mt-2 text-sm font-medium">Not ready yet</p>
      <p className="mx-auto mt-1 max-w-md text-[13px] leading-relaxed text-muted-foreground">{reason}</p>
    </div>
  );
}

function StepCta({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: typeof ListChecks;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-md border border-dashed px-6 py-10 text-center">
      <Icon className="size-7 text-muted-foreground" />
      <div className="space-y-1.5">
        <p className="text-sm font-medium">{title}</p>
        <p className="mx-auto max-w-prose text-[13px] leading-relaxed text-muted-foreground">{description}</p>
      </div>
      {action}
    </div>
  );
}
