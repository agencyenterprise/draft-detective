'use client';

import { AnalysisOptionsMenu } from '@/components/results/components/analysis-options-menu';
import { TabType } from '@/components/results/constants';
import { derivePeerReviewFacts, peerReviewNeedsAttention } from '@/components/results/peer-review/peer-review-derive';
import { ProjectViewProvider } from '@/components/results/project-view-context';
import { PageTitle } from '@/components/shared/page-title';
import { Badge } from '@/components/ui/badge';
import { EditableTitle } from '@/components/ui/editable-title';
import { useExperimentalFeatures } from '@/context/experimental-features-context';
import { useShare } from '@/context/share-context';
import { ProjectFeedbackProvider } from '@/lib/contexts/project-feedback-context';
import { AccessLevel, ProjectDetailed, UserRole, WorkflowRunType } from '@/lib/generated-api';
import { useUserMe } from '@/lib/hooks/use-user-me';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { getWorkflowRunByType, isAnyWorkflowActive } from '@/lib/workflow-state';
import { ReactNode, useMemo } from 'react';
import { AppBar } from './app-bar';
import { NewAssessmentButton } from './new-assessment-button';
import { OldRevisionBanner } from './old-revision-banner';
import { ProjectTab, ProjectTabs } from './project-tabs';
import { ReferenceReviewBanner } from './reference-review-banner';
import { RunActivityIndicator } from './run-activity/run-activity-indicator';
import { RunActivityLine } from './run-activity/run-activity-line';

interface ProjectShellProps {
  projectDetail: ProjectDetailed;
  activeTab: TabType;
  onTabChange: (tab: TabType, hash?: string) => void;
  readOnly?: boolean;
  onTitleSave?: (newTitle: string) => Promise<void>;
  isTitleSaving?: boolean;
  needsReferenceReview?: boolean;
  selectedRevision?: number;
  onRevisionChange?: (revision: number) => void;
  onRevisionCreated?: () => void;
  /**
   * A strip between the project header and the tab, for what the route knows
   * and the shell does not — the share view uses it to tell an owner they are
   * looking at the public version.
   */
  notice?: ReactNode;
  children: ReactNode;
}

/**
 * Workbench chrome: one row for the application, one for the project, and the
 * rest of the viewport for the tab. Every tab manages its own scrolling.
 *
 * The authors line is deliberately absent — it is in the document itself.
 */
export function ProjectShell({
  projectDetail,
  activeTab,
  onTabChange,
  readOnly = false,
  onTitleSave,
  isTitleSaving = false,
  needsReferenceReview = false,
  selectedRevision,
  onRevisionChange,
  onRevisionCreated,
  notice,
  children,
}: ProjectShellProps) {
  const results = useMemo(() => projectDetail.workflow_runs ?? [], [projectDetail.workflow_runs]);
  const { isWorkflowTypeVisible } = useWorkflowTypes();

  const currentRevision = projectDetail.project.current_revision ?? 1;
  const runsActive = isAnyWorkflowActive(results);
  const referenceExtraction = getWorkflowRunByType(results, WorkflowRunType.ReferenceExtraction);

  const { showExperimentalFeatures } = useExperimentalFeatures();
  const peerReviewFacts = derivePeerReviewFacts(projectDetail);
  const peerReviewAttention = peerReviewNeedsAttention(peerReviewFacts, readOnly);

  const tabs: ProjectTab[] = [
    { id: 'document-explorer', label: 'Document Explorer' },
    {
      id: 'references',
      label: 'References',
      count: referenceExtraction?.state?.extracted_references?.length || 0,
      attention: needsReferenceReview,
    },
    { id: 'files', label: 'Files', count: projectDetail.files?.length ?? 0 },
    { id: 'analyses', label: 'Assessments', count: results.filter((r) => isWorkflowTypeVisible(r.run.type)).length },
    // Peer Review is still alpha, so it only exists for users who opted in.
    ...(showExperimentalFeatures
      ? [
          {
            id: 'peer-review' as const,
            label: 'Peer Review',
            count: peerReviewFacts.memos.length > 0 ? peerReviewFacts.memos.length : undefined,
            attention: peerReviewAttention,
          },
        ]
      : []),
  ];

  const titleNode =
    !readOnly && onTitleSave ? (
      <EditableTitle
        title={projectDetail.project.title}
        titleClassName="text-sm font-semibold truncate min-w-0"
        className="min-w-0"
        onSave={onTitleSave}
        isLoading={isTitleSaving}
      />
    ) : (
      <h1 className="truncate text-sm font-semibold">{projectDetail.project.title}</h1>
    );

  // Feedback loads whenever the project is the user's to write to, older revisions
  // included — `readOnly` there is about editing the document, not about rating the
  // issues it found. Admins get it too, on projects shared with them: the ratings are
  // the author's, so they are shown but not theirs to change.
  //
  // Never on the share route, whoever is logged in. A share page has to render what its
  // recipient renders, and the recipient is whoever holds the link — the public endpoint
  // reports READ even to the owner for that reason. Keying off the account instead would
  // make an owner or admin previewing their own link see feedback nobody else does.
  const { shareToken } = useShare();
  const { data: userMe } = useUserMe();
  const isOwner = projectDetail.access_level === AccessLevel.Write;
  const canAccessFeedback = shareToken === null && (isOwner || userMe?.role === UserRole.Admin);

  const navigateToTab = (tab: TabType, hash?: string) => onTabChange(tab, hash);

  return (
    <ProjectFeedbackProvider
      projectId={canAccessFeedback ? projectDetail.project.id : undefined}
      feedbackVisibility={isOwner ? (projectDetail.project.feedback_visibility ?? null) : null}
      readOnly={!isOwner}
    >
      <PageTitle title={projectDetail.project.title} />

      <ProjectViewProvider
        value={{
          projectDetail,
          readOnly,
          selectedRevision,
          onRevisionChange,
          onRevisionCreated,
          navigateToTab,
        }}
      >
        <div className="bg-background text-foreground flex h-dvh flex-col">
          <AppBar title={titleNode} />

          {/* This project: the ways in on the left, what you can do with it on
              the right. The title names the project a row above. */}
          <header className="flex h-12 shrink-0 items-center gap-3 border-b px-3">
            <ProjectTabs tabs={tabs} activeTab={activeTab} onTabChange={onTabChange} />

            {/* Share badge, revision switcher, Export and the overflow menu. */}
            <div className="ml-auto flex shrink-0 items-center gap-2">
              {readOnly && (
                <Badge variant="secondary" className="h-7 text-xs">
                  Read-only view
                </Badge>
              )}
              {/* What is running sits next to what starts a run, so the answer to
                  "did that go?" is where the question was asked. */}
              <RunActivityIndicator projectId={projectDetail.project.id} workflowDetails={results} />
              {!readOnly && <NewAssessmentButton projectId={projectDetail.project.id} />}
              <AnalysisOptionsMenu
                project={projectDetail.project}
                results={results}
                readOnly={readOnly}
                selectedRevision={selectedRevision}
                onRevisionChange={onRevisionChange}
                onRevisionCreated={onRevisionCreated}
                downloadLabel="Export"
                downloadVariant="outline"
                compact
              />
            </div>
          </header>

          <RunActivityLine active={runsActive} />

          {notice}

          {needsReferenceReview && (
            <ReferenceReviewBanner projectDetail={projectDetail} onReviewReferences={() => onTabChange('references')} />
          )}

          {/* An older revision governs every tab, not just the document, so the
              notice belongs to the view rather than to the reader. */}
          {selectedRevision != null && selectedRevision < currentRevision && (
            <OldRevisionBanner
              selectedRevision={selectedRevision}
              currentRevision={currentRevision}
              onViewCurrent={onRevisionChange ? () => onRevisionChange(currentRevision) : undefined}
            />
          )}

          <div className="min-h-0 flex-1">{children}</div>
        </div>
      </ProjectViewProvider>
    </ProjectFeedbackProvider>
  );
}
