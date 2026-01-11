'use client';

import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { DocRenderMode } from '@/lib/constants';
import { ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { useState } from 'react';
import { Card, CardContent } from '../../ui/card';
import { AnalysisOptionsMenu } from './components/analysis-options-menu';
import { ViewModeToggle } from './components/view-mode-toggle';
import { TabType } from './constants';
import { AnalysesTab, FilesTab, ReferencesTab, SummaryTab } from './tabs';
import { DocumentExplorerTab } from './tabs/document-explorer-tab';

interface ResultsVisualizationProps {
  projectDetail: ProjectDetailed;
  viewMode: DocRenderMode;
  onViewModeChange: (mode: DocRenderMode) => void;
  /** When true, hides edit/action controls (for shared view) */
  readOnly?: boolean;
}

export function ResultsVisualization({
  projectDetail,
  viewMode,
  onViewModeChange,
  readOnly = false,
}: ResultsVisualizationProps) {
  const projectId = projectDetail.project.id;
  const results = projectDetail.workflow_runs ?? [];

  const documentProcessing = getWorkflowRunByType(results, WorkflowRunType.DocumentProcessing);
  const referenceExtraction = getWorkflowRunByType(results, WorkflowRunType.ReferenceExtraction);
  const [activeTab, setActiveTab] = useState<TabType>('document-explorer');

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
      case 'analyses':
        return (
          <AnalysesTab
            projectId={projectId}
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
                {referenceExtraction?.state?.references?.length || 0}
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
                {results.length}
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
