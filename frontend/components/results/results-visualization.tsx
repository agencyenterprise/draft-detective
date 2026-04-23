'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Callout } from '@/components/ui/callout';
import { EditableTitle } from '@/components/ui/editable-title';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ProjectFeedbackProvider } from '@/lib/contexts/project-feedback-context';
import { ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useDocumentExplorerStore } from '@/lib/stores/document-explorer-store';
import { cn } from '@/lib/utils';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { format } from 'date-fns';
import { BookOpen, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { AnalysisOptionsMenu } from './components/analysis-options-menu';
import { RevisionSwitcher } from './components/revision-switcher';
import { TabType } from './constants';
import { AnalysesTab, FilesTab, ReferenceReviewTab, SummaryTab } from './tabs';
import { DocumentExplorerTab } from './tabs/document-explorer-tab';
import { UnmatchedReferencesApproveDialog } from './tabs/reference-review/unmatched-references-approve-dialog';
import { useReferenceApprovalFlow } from './tabs/reference-review/use-reference-approval-flow';

interface ResultsVisualizationProps {
  projectDetail: ProjectDetailed;
  /** When true, hides edit/action controls (for shared view) */
  readOnly?: boolean;
  /** Callback for saving title (only used when readOnly=false) */
  onTitleSave?: (newTitle: string) => Promise<void>;
  /** Whether title is currently being saved */
  isTitleSaving?: boolean;
  /** When true, shows the reference review banner indicating approval is needed */
  needsReferenceReview?: boolean;
  /** Currently displayed revision */
  selectedRevision?: number;
  /** Callback when user switches revision */
  onRevisionChange?: (revision: number) => void;
}

export function ResultsVisualization({
  projectDetail,
  readOnly = false,
  onTitleSave,
  isTitleSaving = false,
  needsReferenceReview = false,
  selectedRevision,
  onRevisionChange,
}: ResultsVisualizationProps) {
  const results = projectDetail.workflow_runs ?? [];

  const documentProcessing = getWorkflowRunByType(results, WorkflowRunType.DocumentProcessing);
  const documentSummarization = getWorkflowRunByType(results, WorkflowRunType.DocumentSummarization);
  const referenceExtraction = getWorkflowRunByType(results, WorkflowRunType.ReferenceExtraction);
  const [activeTab, setActiveTab] = useState<TabType>('document-explorer');
  const setFilter = useDocumentExplorerStore((s) => s.setFilter);
  const { isWorkflowTypeVisible } = useWorkflowTypes();

  const referenceApproval = useReferenceApprovalFlow(projectDetail, projectDetail.project.id);

  // Find the main document summary from the summaries list
  const mainFileId = documentProcessing?.state?.file?.file_id;
  const mainSummary = documentSummarization?.state?.summaries?.find((s) => s.file_id === mainFileId);
  const authors = mainSummary?.authors;

  const handleNavigateToDocumentExplorerFromSummary = (workflowType?: WorkflowRunType) => {
    if (workflowType) {
      setFilter({ workflowType: [workflowType] });
    }
    setActiveTab('document-explorer');
  };

  const renderActiveTab = () => {
    switch (activeTab) {
      case 'summary':
        return (
          <SummaryTab
            projectDetail={projectDetail}
            onNavigateToAnalyses={() => setActiveTab('analyses')}
            onNavigateToDocumentExplorer={handleNavigateToDocumentExplorerFromSummary}
          />
        );
      case 'files':
        return <FilesTab projectDetail={projectDetail} readOnly={readOnly} />;
      case 'document-explorer':
        return (
          <DocumentExplorerTab
            projectDetail={projectDetail}
            readOnly={readOnly}
            onNavigateToAnalyses={() => setActiveTab('analyses')}
          />
        );
      case 'references':
        return <ReferenceReviewTab projectId={projectDetail.project.id} readOnly={readOnly} />;
      case 'analyses':
        return (
          <AnalysesTab
            projectDetail={projectDetail}
            readOnly={readOnly}
            onNavigateToDocumentExplorer={(lineRange?: [number, number]) => {
              if (lineRange) {
                const [start, end] = lineRange;
                const hash = start === end ? `#L${start}` : `#L${start}-${end}`;
                window.history.pushState(null, '', hash);
                window.dispatchEvent(new HashChangeEvent('hashchange'));
              }
              setActiveTab('document-explorer');
            }}
            onNavigateToReferences={() => setActiveTab('references')}
          />
        );
    }
  };

  return (
    <ProjectFeedbackProvider
      projectId={readOnly ? undefined : projectDetail.project.id}
      feedbackVisibility={readOnly ? null : (projectDetail.project.feedback_visibility ?? null)}
    >
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <hgroup className="w-full space-y-1">
            {!readOnly && onTitleSave ? (
              <EditableTitle
                title={projectDetail.project.title}
                titleClassName="text-xl font-bold"
                onSave={onTitleSave}
                isLoading={isTitleSaving}
              />
            ) : (
              <h1 className="text-xl font-bold">{projectDetail.project.title}</h1>
            )}
            <h2 className="text-muted-foreground text-sm">
              {authors && <span>{authors} — </span>}
              <span>Project created on {format(projectDetail.project.created_at || new Date(), 'MMM d, yyyy')}</span>
            </h2>
          </hgroup>
        </div>

        {needsReferenceReview && (
          <Callout variant="warning" icon={BookOpen} title="Reference review required">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm min-w-0">
                Go to the <strong>References tab</strong> to upload source documents or fetch them from the web. When
                you&apos;re ready, use <strong>Approve and start assessment</strong> here or at the bottom of that tab.
              </p>
              <div className="flex shrink-0 flex-wrap items-center gap-2">
                <Button size="sm" variant="outline" onClick={() => setActiveTab('references')}>
                  Review References
                </Button>
                <Button
                  size="sm"
                  onClick={referenceApproval.handleApprove}
                  disabled={referenceApproval.isApproveDisabled}
                >
                  {referenceApproval.showApproveButtonSpinner && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                  )}
                  {referenceApproval.approveButtonText}
                </Button>
              </div>
            </div>
            <UnmatchedReferencesApproveDialog
              open={referenceApproval.showUnmatchedWarning}
              onOpenChange={referenceApproval.setShowUnmatchedWarning}
              unmatchedCount={referenceApproval.unmatchedCount}
              onConfirmApprove={referenceApproval.handleConfirmApprove}
            />
          </Callout>
        )}

        <div className="flex flex-col gap-2 md:items-center md:justify-between md:flex-row">
          <Tabs
            defaultValue="document-explorer"
            value={activeTab}
            onValueChange={(value) => setActiveTab(value as TabType)}
          >
            <TabsList>
              <TabsTrigger value="document-explorer">Document Explorer</TabsTrigger>
              <TabsTrigger value="summary">Summary</TabsTrigger>
              <TabsTrigger value="references" className="relative">
                References{' '}
                <Badge className="rounded-full h-4.5 min-w-4.5" variant="secondary">
                  {referenceExtraction?.state?.extracted_references?.length || 0}
                </Badge>
                {needsReferenceReview && (
                  <span className="absolute -top-1 -right-1 h-2.5 w-2.5 rounded-full bg-amber-500 ring-2 ring-background" />
                )}
              </TabsTrigger>
              <TabsTrigger value="files">
                Files{' '}
                <Badge className="rounded-full h-4.5 min-w-4.5" variant="secondary">
                  {projectDetail.files?.length ?? 0}
                </Badge>
              </TabsTrigger>
              <TabsTrigger value="analyses">
                Assessments{' '}
                <Badge className="rounded-full h-4.5 min-w-4.5" variant="secondary">
                  {results.filter((r) => isWorkflowTypeVisible(r.run.type)).length}
                </Badge>
              </TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="flex items-center gap-2">
            {selectedRevision && onRevisionChange && (
              <RevisionSwitcher
                currentRevision={projectDetail.project.current_revision ?? 1}
                totalRevisions={projectDetail.project.current_revision ?? 1}
                selectedRevision={selectedRevision}
                onRevisionChange={onRevisionChange}
              />
            )}
            {readOnly && (
              <Badge variant="secondary" className="text-xs">
                Read-only view
              </Badge>
            )}
            <AnalysisOptionsMenu project={projectDetail.project} results={results} readOnly={readOnly} />
          </div>
        </div>

        <div
          className={cn('border rounded-lg shadow-sm p-4', {
            'h-[calc(100vh-13rem)] p-0': activeTab === 'document-explorer',
          })}
        >
          {renderActiveTab()}
        </div>
      </div>
    </ProjectFeedbackProvider>
  );
}
