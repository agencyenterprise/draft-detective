'use client';

import { Badge } from '@/components/ui/badge';
import { EditableTitle } from '@/components/ui/editable-title';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { DocRenderMode } from '@/lib/constants';
import { ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { format } from 'date-fns';
import { useState } from 'react';
import { Card, CardContent } from '../../ui/card';
import { AnalysisOptionsMenu } from './components/analysis-options-menu';
import { ViewModeToggle } from './components/view-mode-toggle';
import { TabType } from './constants';
import { AnalysesTab, FilesTab, ReferenceReviewTab, ReferencesTab, SummaryTab } from './tabs';
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
  const projectId = projectDetail.project.id;
  const results = projectDetail.workflow_runs ?? [];

  const documentProcessing = getWorkflowRunByType(results, WorkflowRunType.DocumentProcessing);
  const referenceExtraction = getWorkflowRunByType(results, WorkflowRunType.ReferenceExtraction);
  const [activeTab, setActiveTab] = useState<TabType>('document-explorer');
  const { isWorkflowTypeVisible } = useWorkflowTypes();

  const authors = documentProcessing?.state?.main_document_summary?.authors;

  const renderActiveTab = () => {
    switch (activeTab) {
      case 'summary':
        return <SummaryTab allWorkflowDetails={results} />;
      case 'references':
        return <ReferencesTab projectId={projectId} allWorkflowDetails={results} readOnly={readOnly} />;
      case 'files':
        return <FilesTab projectId={projectId} allWorkflowDetails={results} />;
      case 'document-explorer':
        return (
          <DocumentExplorerTab
            projectId={projectId}
            allWorkflowDetails={results}
            issues={projectDetail.issues ?? []}
            viewMode={viewMode}
            readOnly={readOnly}
            onNavigateToAnalyses={() => setActiveTab('analyses')}
          />
        );
      case 'reference-review':
        return <ReferenceReviewTab projectId={projectId} allWorkflowDetails={results} readOnly={readOnly} />;
      case 'analyses':
        return (
          <AnalysesTab
            project={projectDetail}
            readOnly={readOnly}
            onNavigateToDocumentExplorer={() => setActiveTab('document-explorer')}
            onNavigateToReferences={() => setActiveTab('references')}
          />
        );
    }
  };

  const isDoclingAvailable = !!(
    documentProcessing?.state?.file?.docling_pages && documentProcessing?.state?.chunk_to_items?.mapping
  );

  return (
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
            <TabsTrigger value="reference-review">
              References & Files{' '}
              <Badge className="rounded-full h-4.5 min-w-4.5" variant="secondary">
                {referenceExtraction?.state?.extracted_references?.length || 0}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="files">
              Files{' '}
              <Badge className="rounded-full h-4.5 min-w-4.5" variant="secondary">
                {projectDetail.files_count}
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
          <AnalysisOptionsMenu project={projectDetail.project} results={results} readOnly={readOnly} />
        </div>
      </div>

      <Card>
        <CardContent className={activeTab === 'document-explorer' ? 'h-[calc(100vh-17.5rem)]' : ''}>
          {renderActiveTab()}
        </CardContent>
      </Card>
    </div>
  );
}
