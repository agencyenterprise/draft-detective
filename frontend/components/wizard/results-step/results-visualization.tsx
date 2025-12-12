'use client';

import { Dialog } from '@/components/ui/dialog';
import { analysisService } from '@/lib/analysis-service';
import { DocRenderMode } from '@/lib/constants';
import { downloadFile, generateEvalFilename } from '@/lib/file-download';
import {
  rerunAnalysisEndpointApiRerunAnalysisPost,
  RerunAnalysisRequest,
  WorkflowRunDetail,
  WorkflowRunType,
} from '@/lib/generated-api';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';
import { Card, CardContent } from '../../ui/card';
import { TabNavigation } from './components';
import { AnalysisOptionsMenu } from './components/analysis-options-menu';
import { ReevaluationDialogContent, ReevaluationFormValues } from './components/reevaluation-dialog-content';
import { ViewModeToggle } from './components/view-mode-toggle';
import { TabType } from './constants';
import {
  FilesTab,
  LiteratureReviewTab,
  LiveReportsTab,
  MethodologicalAlignmentTab,
  ReferencesTab,
  SummaryTab,
} from './tabs';
import { DocumentExplorerTab } from './tabs/document-explorer-tab';

interface ResultsVisualizationProps {
  projectId: string;
  results: WorkflowRunDetail[];
  isProcessing?: boolean;
  viewMode: DocRenderMode;
  onViewModeChange: (mode: DocRenderMode) => void;
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
  /** When true, hides edit/action controls (for shared view) */
  readOnly?: boolean;
}

export function ResultsVisualization({
  projectId,
  results,
  isProcessing = false,
  viewMode,
  onViewModeChange,
  activeTab,
  onTabChange,
  readOnly = false,
}: ResultsVisualizationProps) {
  const claimSubstantiationResults = getWorkflowRunByType(results, WorkflowRunType.ClaimSubstantiation);
  const methodologicalAlignmentResults = getWorkflowRunByType(results, WorkflowRunType.MethodologicalAlignment);
  const literatureReviewResults = getWorkflowRunByType(results, WorkflowRunType.LiteratureReview);
  const liveReportsResults = getWorkflowRunByType(results, WorkflowRunType.LiveReports);
  const claimSubstantiationStateSummary = claimSubstantiationResults?.state;

  const [isReevaluationDialogOpen, setIsReevaluationDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const reevaluateMutation = useMutation({
    mutationFn: async (request: RerunAnalysisRequest) => {
      return await rerunAnalysisEndpointApiRerunAnalysisPost({
        body: request,
      });
    },
    onSuccess: (_data, variables) => {
      setIsReevaluationDialogOpen(false);

      // Invalidate queries to show loading state
      queryClient.invalidateQueries({
        queryKey: ['chunkDetails'],
      });
      queryClient.invalidateQueries({
        queryKey: ['project', variables.project_id],
      });
    },
    onError: (error) => {
      console.error('Re-evaluation failed:', error);
      toast.error(error instanceof Error ? error.message : 'Re-evaluation failed');
    },
  });

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

  const handleReevaluate = (values: ReevaluationFormValues) => {
    if (!claimSubstantiationStateSummary) return;

    reevaluateMutation.mutate({
      project_id: projectId,
      config: {
        ...claimSubstantiationStateSummary?.config,
        target_chunk_indices: values.targetChunkIndices,
        agents_to_run: values.selectedAgents,
        openai_api_key: values.openaiApiKey,
      },
    });
  };

  const renderActiveTab = () => {
    switch (activeTab) {
      case 'summary':
        return <SummaryTab workflowDetail={claimSubstantiationResults} isProcessing={isProcessing} />;
      case 'references':
        return <ReferencesTab workflowDetail={claimSubstantiationResults} isProcessing={isProcessing} />;
      case 'literature_review':
        return (
          <LiteratureReviewTab workflowDetail={literatureReviewResults} projectId={projectId} readOnly={readOnly} />
        );
      case 'live_reports':
        return <LiveReportsTab workflowDetail={liveReportsResults} projectId={projectId} readOnly={readOnly} />;
      case 'files':
        return <FilesTab projectId={projectId} />;
      case 'document-explorer':
        return (
          <DocumentExplorerTab
            projectId={projectId}
            workflowDetail={claimSubstantiationResults}
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
          {!readOnly && (
            <AnalysisOptionsMenu
              onSaveAsEvalTest={handleSaveAsEvalTest}
              onReevaluate={() => setIsReevaluationDialogOpen(true)}
              projectId={projectId}
              results={results}
            />
          )}
        </div>
      </div>

      <Card>
        <CardContent className={activeTab === 'document-explorer' ? 'h-[calc(100vh-17.5rem)]' : ''}>
          {renderActiveTab()}
        </CardContent>
      </Card>

      {!readOnly && (
        <Dialog open={isReevaluationDialogOpen} onOpenChange={setIsReevaluationDialogOpen}>
          <ReevaluationDialogContent
            isPending={false}
            onCancel={() => setIsReevaluationDialogOpen(false)}
            onConfirm={handleReevaluate}
          />
        </Dialog>
      )}
    </div>
  );
}
