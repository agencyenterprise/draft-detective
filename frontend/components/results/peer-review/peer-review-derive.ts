/**
 * Derives everything the Peer Review tab needs from the project overview.
 *
 * Deliberately pure and React-free: these predicates mirror server-side
 * prechecks, and the point of keeping them in one file is that they can be read
 * side by side with the Python. A blocked run still *succeeds* on the backend,
 * returning a one-paragraph HTML guard message that is indistinguishable from a
 * real report inside the iframe, so the client has to refuse to start rather
 * than start and render something that looks like a result.
 *
 * Mirrored from:
 * - `get_latest_reviewer_memo_revision()` — lib/services/file_artifacts_service/file_artifacts_service.py
 * - `precheck()` in lib/workflows/{revision_planning_summary,reviewer_response_memos,reviewer_coverage_report}/manifest.py
 * - the response-memo folder the coverage report reads — lib/workflows/reviewer_coverage_report/manifest.py
 */

import {
  FileListItem,
  FileRole,
  ProjectOverview,
  WorkflowRunStatus,
  WorkflowRunSummary,
  WorkflowRunType,
} from '@/lib/generated-api';
import { findRunByType, getDisplayStatus } from '@/lib/workflow-state';

/** The step runs as the overview lists them; a step fetches its run's state when shown. */
export interface PeerReviewRuns {
  plan?: WorkflowRunSummary;
  memos?: WorkflowRunSummary;
  coverage?: WorkflowRunSummary;
}

export interface PeerReviewFacts {
  currentRevision: number;
  viewedRevision: number;
  isViewingOldRevision: boolean;

  /** Every reviewer memo in the project, across all revisions. */
  memos: FileListItem[];
  /** The revision the assessments will read memos from, or null when there are none. */
  reviewedRevision: number | null;
  /** Memos on `reviewedRevision` — the ones that will actually be read. */
  activeMemos: FileListItem[];
  /** Revisions holding memos the agent will ignore, newest first. */
  staleMemoRevisions: number[];

  /** Every response memo the author uploaded, across all revisions. */
  responseMemos: FileListItem[];
  /** Response memos on the current revision — the ones the coverage report reads. */
  activeResponseMemos: FileListItem[];
  /**
   * Uploading a response memo only makes sense against a revised draft: the
   * upload always attaches to the current revision, and before a revised draft
   * exists that is still the one the reviewers read.
   */
  canUploadResponses: boolean;
  /**
   * An active response memo arrived after the coverage report finished, so
   * the report on screen did not read it. Measured against completion, not
   * creation: the run reads its file tree some time after it is queued, so a
   * memo uploaded while it ran may or may not have been read, and the warning
   * only fires when it certainly was not.
   */
  responsesNewerThanCoverage: boolean;

  reviewedMain?: FileListItem;
  currentMain?: FileListItem;
  hasRevisedDraft: boolean;

  documentProcessingReady: boolean;

  planBlockedReason: string | null;
  reviseBlockedReason: string | null;
  /**
   * Blocks both draft-comparing steps — the response memos and the coverage
   * report. They are separate steps in the UI but their backend prechecks are
   * identical, so one reason serves both rather than two copies drifting apart.
   */
  comparisonBlockedReason: string | null;

  runs: PeerReviewRuns;
}

export function derivePeerReviewFacts(overview: ProjectOverview): PeerReviewFacts {
  const files = overview.files ?? [];
  const workflowRuns = overview.workflow_runs ?? [];

  const currentRevision = overview.project.current_revision ?? 1;
  // `overview.revision` is the revision the API actually returned, which is
  // more reliable than the selectedRevision prop (the share page never sends one).
  const viewedRevision = overview.revision ?? currentRevision;
  const isViewingOldRevision = viewedRevision < currentRevision;

  // Mirrors get_latest_reviewer_memo_revision(): every memo, drop null revisions,
  // take the max. `overview.files` spans all revisions.
  const memos = files.filter((f) => f.role === FileRole.ReviewerMemo);
  const memoRevisions = memos.map((f) => f.revision).filter((r): r is number => r != null);
  const reviewedRevision = memoRevisions.length > 0 ? Math.max(...memoRevisions) : null;
  const activeMemos = memos.filter((f) => f.revision === reviewedRevision);
  const staleMemoRevisions = [...new Set(memoRevisions)].filter((r) => r !== reviewedRevision).sort((a, b) => b - a);

  const mainByRevision = new Map<number, FileListItem>();
  for (const file of files) {
    if (file.role === FileRole.Main && file.revision != null) mainByRevision.set(file.revision, file);
  }
  const currentMain = mainByRevision.get(currentRevision);
  const reviewedMain = reviewedRevision != null ? mainByRevision.get(reviewedRevision) : undefined;
  // The precheck compares main file IDs, not revision numbers. Mirror that.
  // Note this is against currentRevision, never viewedRevision: a run always
  // executes at the current revision regardless of what is on screen.
  const hasRevisedDraft = !!currentMain && !!reviewedMain && currentMain.id !== reviewedMain.id;

  // All three declare required_dependencies = [DOCUMENT_PROCESSING], and starting
  // a run whose dependency has not completed errors out. There is a real window
  // right after a new revision where the main file exists but processing is not done.
  const documentProcessing = findRunByType(workflowRuns, WorkflowRunType.DocumentProcessing);
  const documentProcessingReady =
    !!documentProcessing && getDisplayStatus(documentProcessing) === WorkflowRunStatus.Completed;

  // Uploads always land on the current revision, and the coverage report
  // reads only that revision's folder, so older ones are ignored.
  const responseMemos = files.filter((f) => f.role === FileRole.ResponseMemo);
  const activeResponseMemos = responseMemos.filter((f) => f.revision === currentRevision);
  const canUploadResponses = hasRevisedDraft && !isViewingOldRevision;

  const coverageRun = findRunByType(workflowRuns, WorkflowRunType.ReviewerCoverageReport);
  // Generated types say Date, but the wire value is an ISO string.
  const coverageCompletedAt = coverageRun?.run.completed_at ? new Date(coverageRun.run.completed_at).getTime() : null;
  const responsesNewerThanCoverage =
    coverageCompletedAt !== null &&
    activeResponseMemos.some((f) => new Date(f.created_at).getTime() > coverageCompletedAt);

  const noMemos = reviewedRevision === null;

  // Runs always execute at the current revision, but `workflow_runs` above is
  // scoped to the revision on screen — so while an older one is being viewed we
  // cannot know whether the current revision is ready, and every readiness
  // signal here would be about the wrong revision. Block outright and say so
  // rather than report a status that is not about the draft a run would use.
  // (Viewing an older revision also forces readOnly, so no action is offered
  // either way; this keeps the derived state from lying about it.)
  const staleRevisionReason = isViewingOldRevision
    ? `You are viewing revision ${viewedRevision}. These assessments always run against revision ${currentRevision} — switch to it to run them.`
    : null;

  const planBlockedReason =
    staleRevisionReason ??
    (noMemos
      ? 'Upload at least one reviewer memo to generate a revision-planning summary.'
      : !documentProcessingReady
        ? 'Waiting for the document to finish processing.'
        : null);

  const reviseBlockedReason = staleRevisionReason ?? (noMemos ? 'Waiting on reviewer memos.' : null);

  const comparisonBlockedReason =
    staleRevisionReason ??
    (noMemos
      ? 'Upload at least one reviewer memo first.'
      : // Not a precheck mirror but a crash guard: get_main_file(revision=R) raises
        // ValueError when the revision has no main, failing the run outright.
        !reviewedMain
        ? `Revision ${reviewedRevision} has no main document on record, so there is nothing to compare against.`
        : !hasRevisedDraft
          ? `Your memos are attached to revision ${reviewedRevision}, which is still the current draft. Upload your revised draft as a new revision in step 2 — or, if the memos reviewed an earlier draft, re-upload them targeting that revision.`
          : !documentProcessingReady
            ? 'Waiting for the revised draft to finish processing.'
            : null);

  return {
    currentRevision,
    viewedRevision,
    isViewingOldRevision,
    memos,
    reviewedRevision,
    activeMemos,
    staleMemoRevisions,
    responseMemos,
    activeResponseMemos,
    canUploadResponses,
    responsesNewerThanCoverage,
    reviewedMain,
    currentMain,
    hasRevisedDraft,
    documentProcessingReady,
    planBlockedReason,
    reviseBlockedReason,
    comparisonBlockedReason,
    runs: {
      plan: findRunByType(workflowRuns, WorkflowRunType.RevisionPlanningSummary),
      memos: findRunByType(workflowRuns, WorkflowRunType.ReviewerResponseMemos),
      coverage: coverageRun,
    },
  };
}

/** True when a stage is actionable and nobody has acted on it, or a run failed. */
export function peerReviewNeedsAttention(facts: PeerReviewFacts, readOnly: boolean): boolean {
  if (readOnly || facts.reviewedRevision === null) return false;
  const { plan, memos, coverage } = facts.runs;
  const failed = [plan, memos, coverage].some((run) => run && getDisplayStatus(run) === WorkflowRunStatus.Failed);
  // When the memos belong to an earlier revision the planning summary usually
  // lives there too, and the tab falls back to showing it. This runs outside
  // that fetch, so treat "no plan on this revision" as actionable only when
  // there is no earlier revision it could have come from — otherwise the tab
  // would show an attention dot next to a summary that is right there.
  const planCouldExistElsewhere = facts.reviewedRevision !== facts.viewedRevision;
  const planActionable = facts.planBlockedReason === null && !plan && !planCouldExistElsewhere;
  const hasResponses = !!memos || facts.activeResponseMemos.length > 0;
  const respondActionable = facts.comparisonBlockedReason === null && (!hasResponses || !coverage);
  return failed || planActionable || respondActionable;
}
