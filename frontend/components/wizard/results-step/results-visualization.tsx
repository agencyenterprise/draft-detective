'use client';

import { BatchFeedbackProvider } from '@/components/batch-feedback-provider';
import { Badge } from '@/components/ui/badge';
import { EditableTitle } from '@/components/ui/editable-title';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { DocRenderMode } from '@/lib/constants';
import { ProjectDetailed, SeverityEnum, WorkflowRunType } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { cn } from '@/lib/utils';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { format } from 'date-fns';
import { useMemo, useState } from 'react';
import { AnalysisOptionsMenu } from './components/analysis-options-menu';
import { ViewModeToggle } from './components/view-mode-toggle';
import { TabType } from './constants';
import { AnalysesTab, FilesTab, ReferenceReviewTab, SummaryTab } from './tabs';
import { DocumentExplorerTab } from './tabs/document-explorer-tab';

interface ResultsVisualizationProps {
  projectDetail: ProjectDetailed;
  viewMode: DocRenderMode;
  onViewModeChange: (mode: DocRenderMode) => void;
  /** When true, hides edit/action controls (for shared view) */
  readOnly?: boolean;
  /** Callback for saving title (only used when readOnly=false) */
  onTitleSave?: (newTitle: string) => Promise<void>;
  /** Whether title is currently being saved */
  isTitleSaving?: boolean;
}

export function ResultsVisualization({
  projectDetail,
  viewMode,
  onViewModeChange,
  readOnly = false,
  onTitleSave,
  isTitleSaving = false,
}: ResultsVisualizationProps) {
  const results = projectDetail.workflow_runs ?? [];

  const documentProcessing = getWorkflowRunByType(results, WorkflowRunType.DocumentProcessing);
  const chunkSplitting = getWorkflowRunByType(results, WorkflowRunType.ChunkSplitting);
  const documentSummarization = getWorkflowRunByType(results, WorkflowRunType.DocumentSummarization);
  const referenceExtraction = getWorkflowRunByType(results, WorkflowRunType.ReferenceExtraction);
  const [activeTab, setActiveTab] = useState<TabType>('document-explorer');
  const [severityFilter, setSeverityFilter] = useState<SeverityEnum[]>([]);
  const [workflowTypeFilter, setWorkflowTypeFilter] = useState<WorkflowRunType[]>([]);
  const { isWorkflowTypeVisible } = useWorkflowTypes();

  // Collect all workflow run IDs for batch feedback fetching
  const workflowRunIds = useMemo(() => results.map((r) => r.run.id).filter(Boolean), [results]);

  // Find the main document summary from the summaries list
  const mainFileId = documentProcessing?.state?.file?.file_id;
  const mainSummary = documentSummarization?.state?.summaries?.find((s) => s.file_id === mainFileId);
  const authors = mainSummary?.authors;

  const handleNavigateToDocumentExplorerFromSummary = (workflowType?: WorkflowRunType) => {
    if (workflowType) {
      setWorkflowTypeFilter([workflowType]);
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
        return <FilesTab projectDetail={projectDetail} />;
      case 'document-explorer':
        return (
          <DocumentExplorerTab
            projectDetail={projectDetail}
            viewMode={viewMode}
            readOnly={readOnly}
            severityFilter={severityFilter}
            onSeverityFilterChange={setSeverityFilter}
            workflowTypeFilter={workflowTypeFilter}
            onWorkflowTypeFilterChange={setWorkflowTypeFilter}
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
            onNavigateToDocumentExplorer={(chunkIndices?: number[]) => {
              if (chunkIndices && chunkIndices.length > 0) {
                window.history.pushState(null, '', `#chunks-${chunkIndices.join(',')}`);
                window.dispatchEvent(new HashChangeEvent('hashchange'));
              }
              setActiveTab('document-explorer');
            }}
            onNavigateToReferences={() => setActiveTab('references')}
          />
        );
    }
  };

  const isDoclingAvailable = !!(
    documentProcessing?.state?.file?.docling_pages && chunkSplitting?.state?.chunk_to_items?.mapping
  );

  return (
    <BatchFeedbackProvider workflowRunIds={workflowRunIds}>
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

        <div className="flex flex-col gap-2 md:items-center md:justify-between md:flex-row">
          <Tabs
            defaultValue="document-explorer"
            value={activeTab}
            onValueChange={(value) => setActiveTab(value as TabType)}
          >
            <TabsList>
              <TabsTrigger value="document-explorer">Document Explorer</TabsTrigger>
              <TabsTrigger value="summary">Summary</TabsTrigger>
              <TabsTrigger value="references">
                References{' '}
                <Badge className="rounded-full h-4.5 min-w-4.5" variant="secondary">
                  {referenceExtraction?.state?.extracted_references?.length || 0}
                </Badge>
              </TabsTrigger>
              <TabsTrigger value="files">
                Files{' '}
                <Badge className="rounded-full h-4.5 min-w-4.5" variant="secondary">
                  {projectDetail.files?.length ?? 0}
                </Badge>
              </TabsTrigger>
              <TabsTrigger value="analyses">
                Analyses{' '}
                <Badge className="rounded-full h-4.5 min-w-4.5" variant="secondary">
                  {results.filter((r) => isWorkflowTypeVisible(r.run.type)).length}
                </Badge>
              </TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="flex items-center gap-1">
            {activeTab === 'document-explorer' && (
              <ViewModeToggle
                onViewModeChange={onViewModeChange}
                viewMode={viewMode}
                isDoclingAvailable={isDoclingAvailable}
              />
            )}
            {readOnly && (
              <Badge variant="secondary" className="text-xs">
                Read-only view
              </Badge>
            )}
            <AnalysisOptionsMenu
              project={projectDetail.project}
              results={results}
              readOnly={readOnly}
              severityFilter={severityFilter}
              workflowTypeFilter={workflowTypeFilter}
            />
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
    </BatchFeedbackProvider>
  );
}
