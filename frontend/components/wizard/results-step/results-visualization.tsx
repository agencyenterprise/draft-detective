'use client';

import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { analysisService } from '@/lib/analysis-service';
import { DocRenderMode } from '@/lib/constants';
import { downloadFile, generateEvalFilename } from '@/lib/file-download';
import { ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { Card, CardContent } from '../../ui/card';
import { AnalysisOptionsMenu } from './components/analysis-options-menu';
import { ViewModeToggle } from './components/view-mode-toggle';
import { TabType } from './constants';
import { AnalysesTab, FilesTab, ReferencesTab, SummaryTab } from './tabs';
import { DocumentExplorerTab } from './tabs/document-explorer-tab';
import { useState } from 'react';

interface ResultsVisualizationProps {
  projectDetail: ProjectDetailed;
  isProcessing?: boolean;
  viewMode: DocRenderMode;
  onViewModeChange: (mode: DocRenderMode) => void;
  /** When true, hides edit/action controls (for shared view) */
  readOnly?: boolean;
}

export function ResultsVisualization({
  projectDetail,
  isProcessing = false,
  viewMode,
  onViewModeChange,
  readOnly = false,
}: ResultsVisualizationProps) {
  const projectId = projectDetail.project.id;
  const results = projectDetail.workflow_runs ?? [];

  const claimSubstantiationResults = getWorkflowRunByType(results, WorkflowRunType.ClaimSubstantiation);
  const referenceValidationResults = getWorkflowRunByType(results, WorkflowRunType.ReferenceValidation);
  const claimSubstantiationStateSummary = claimSubstantiationResults?.state;
  const [activeTab, setActiveTab] = useState<TabType>('document-explorer');

  const handleSaveAsEvalTest = async () => {
    if (!claimSubstantiationStateSummary) return;

    try {
      const testName = `eval_${Date.now()}`;
      const description = `Generated from analysis results on ${new Date().toLocaleDateString()}`;

      const blob = await analysisService.generateEvalPackage(claimSubstantiationStateSummary, testName, description);

      const filename = generateEvalFilename(testName);
      downloadFile({ filename, blob });
    } catch (error) {
      console.error('Failed to generate eval test package:', error);
    }
  };

  const renderActiveTab = () => {
    switch (activeTab) {
      case 'summary':
        return <SummaryTab workflowDetail={claimSubstantiationResults} isProcessing={isProcessing} />;
      case 'references':
        return (
          <ReferencesTab
            workflowDetail={claimSubstantiationResults}
            referenceValidationDetail={referenceValidationResults}
            projectId={projectId}
            isProcessing={isProcessing}
            readOnly={readOnly}
          />
        );
      case 'files':
        return <FilesTab projectId={projectId} />;
      case 'document-explorer':
        return (
          <DocumentExplorerTab
            projectId={projectId}
            allWorkflowDetails={results}
            issues={projectDetail.issues ?? []}
            isProcessing={isProcessing}
            viewMode={viewMode}
            readOnly={readOnly}
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
    claimSubstantiationStateSummary?.file?.docling_pages && claimSubstantiationStateSummary?.chunk_to_items?.mapping
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
                {claimSubstantiationResults?.state?.references?.length}
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
          <AnalysisOptionsMenu
            onSaveAsEvalTest={handleSaveAsEvalTest}
            project={projectDetail.project}
            results={results}
            readOnly={readOnly}
          />
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
