'use client';

import { analysisService } from '@/lib/analysis-service';
import { DocRenderMode } from '@/lib/constants';
import { downloadFile, generateEvalFilename } from '@/lib/file-download';
import { ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { Card, CardContent } from '../../ui/card';
import { TabNavigation } from './components';
import { AnalysisOptionsMenu } from './components/analysis-options-menu';
import { ViewModeToggle } from './components/view-mode-toggle';
import { TabType } from './constants';
import {
  CitationSuggesterTab,
  FilesTab,
  LiteratureReviewTab,
  LiveReportsTab,
  MethodologicalAlignmentTab,
  ReferencesTab,
  SummaryTab,
} from './tabs';
import { DocumentExplorerTab } from './tabs/document-explorer-tab';

interface ResultsVisualizationProps {
  projectDetail: ProjectDetailed;
  isProcessing?: boolean;
  viewMode: DocRenderMode;
  onViewModeChange: (mode: DocRenderMode) => void;
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
  /** When true, hides edit/action controls (for shared view) */
  readOnly?: boolean;
}

export function ResultsVisualization({
  projectDetail,
  isProcessing = false,
  viewMode,
  onViewModeChange,
  activeTab,
  onTabChange,
  readOnly = false,
}: ResultsVisualizationProps) {
  const projectId = projectDetail.project.id;
  const results = projectDetail.workflow_runs ?? [];

  const claimSubstantiationResults = getWorkflowRunByType(results, WorkflowRunType.ClaimSubstantiation);
  const methodologicalAlignmentResults = getWorkflowRunByType(results, WorkflowRunType.MethodologicalAlignment);
  const literatureReviewResults = getWorkflowRunByType(results, WorkflowRunType.LiteratureReview);
  const citationSuggesterResults = getWorkflowRunByType(results, WorkflowRunType.CitationSuggester);
  const liveReportsResults = getWorkflowRunByType(results, WorkflowRunType.LiveReports);
  const referenceValidationResults = getWorkflowRunByType(results, WorkflowRunType.ReferenceValidation);
  const claimSubstantiationStateSummary = claimSubstantiationResults?.state;

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
      case 'literature_review':
        return (
          <LiteratureReviewTab workflowDetail={literatureReviewResults} projectId={projectId} readOnly={readOnly} />
        );
      case 'citation_suggester':
        return (
          <CitationSuggesterTab workflowDetail={citationSuggesterResults} projectId={projectId} readOnly={readOnly} />
        );
      case 'live_reports':
        return <LiveReportsTab workflowDetail={liveReportsResults} projectId={projectId} readOnly={readOnly} />;
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
      case 'methodological_alignment':
        return (
          <MethodologicalAlignmentTab
            results={methodologicalAlignmentResults}
            projectId={projectId}
            readOnly={readOnly}
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
        <TabNavigation activeTab={activeTab} onTabChange={onTabChange} />
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
            projectId={projectId}
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
