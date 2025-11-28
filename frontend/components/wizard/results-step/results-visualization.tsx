'use client';

import { Dialog } from '@/components/ui/dialog';
import { analysisService } from '@/lib/analysis-service';
import { DocRenderMode } from '@/lib/constants';
import { downloadFile, generateEvalFilename } from '@/lib/file-download';
import { ClaimSubstantiatorStateSummary, RerunAnalysisRequest } from '@/lib/generated-api';
import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../ui/card';
import { TabNavigation } from './components';
import { AnalysisOptionsMenu } from './components/analysis-options-menu';
import { DownloadDocxButton } from './components/download-docx-button';
import { ReevaluationDialogContent, ReevaluationFormValues } from './components/reevaluation-dialog-content';
import { ViewModeToggle } from './components/view-mode-toggle';
import { TabType } from './constants';
import { useResultsCalculations } from './hooks/use-results-calculations';
import {
  FilesTab,
  LiteratureReviewTab,
  LiveReportsTab,
  ReferencesTab,
  SummaryTab,
  MethodologicalAlignmentTab,
} from './tabs';
import { DocumentExplorerTab } from './tabs/document-explorer-tab';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { analysisApi } from '@/lib/api';

interface ResultsVisualizationProps {
  projectId: string;
  results: ClaimSubstantiatorStateSummary | undefined;
  isProcessing?: boolean;
  viewMode: DocRenderMode;
  onViewModeChange: (mode: DocRenderMode) => void;
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
}

export function ResultsVisualization({
  projectId,
  results,
  isProcessing = false,
  viewMode,
  onViewModeChange,
  activeTab,
  onTabChange,
}: ResultsVisualizationProps) {
  const calculations = useResultsCalculations(results);
  const [isReevaluationDialogOpen, setIsReevaluationDialogOpen] = useState(false);

  const reevaluateMutation = useMutation({
    mutationFn: async (request: RerunAnalysisRequest) => {
      return await analysisApi.rerunAnalysisEndpointApiRerunAnalysisPost({
        rerunAnalysisRequest: request,
      });
    },
    onSuccess: (_data, variables, context, { client }) => {
      setIsReevaluationDialogOpen(false);

      // Invalidate queries to show loading state
      client.invalidateQueries({
        queryKey: ['chunkDetails'],
      });
      client.invalidateQueries({
        queryKey: ['project', variables.projectId],
      });
    },
    onError: (error) => {
      console.error('Re-evaluation failed:', error);
      toast.error(error instanceof Error ? error.message : 'Re-evaluation failed');
    },
  });

  const handleSaveAsEvalTest = async () => {
    if (!results) return;

    try {
      const testName = `eval_${Date.now()}`;
      const description = `Generated from analysis results on ${new Date().toLocaleDateString()}`;

      const blob = await analysisService.generateEvalPackage(results, testName, description);

      const filename = generateEvalFilename(testName);
      downloadFile({ filename, blob });
    } catch (error) {
      console.error('Failed to generate eval test package:', error);
    }
  };

  const handleReevaluate = (values: ReevaluationFormValues) => {
    reevaluateMutation.mutate({
      projectId,
      config: {
        ...results?.config,
        targetChunkIndices: values.targetChunkIndices,
        agentsToRun: values.selectedAgents,
        openaiApiKey: values.openaiApiKey,
      },
    });
  };

  if (!results) {
    return (
      <Card className="max-w-4xl mx-auto">
        <CardHeader>
          <CardTitle>No Results Available</CardTitle>
          <CardDescription>No analysis results to display</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const renderActiveTab = () => {
    switch (activeTab) {
      case 'summary':
        return (
          <SummaryTab
            results={results}
            totalChunks={calculations.totalChunks}
            chunksWithClaims={calculations.chunksWithClaims}
            chunksWithCitations={calculations.chunksWithCitations}
            supportedReferences={calculations.supportedReferences}
            totalClaims={calculations.totalClaims}
            totalCitations={calculations.totalCitations}
            totalUnsubstantiated={calculations.totalUnsubstantiated}
            isProcessing={isProcessing}
          />
        );
      case 'references':
        return <ReferencesTab results={results} isProcessing={isProcessing} />;
      case 'literature_review':
        return <LiteratureReviewTab results={results} isProcessing={isProcessing} />;
      case 'live_reports':
        return <LiveReportsTab results={results} isProcessing={isProcessing} />;
      case 'files':
        return <FilesTab results={results} />;
      case 'document-explorer':
        return (
          <DocumentExplorerTab
            projectId={projectId}
            results={results}
            isProcessing={isProcessing}
            viewMode={viewMode}
          />
        );
      case 'methodological_alignment':
        return <MethodologicalAlignmentTab results={results} isProcessing={isProcessing} />;
    }
  };

  const isDoclingAvailable = !!(results?.file?.doclingPages && results?.chunkToItems?.mapping);

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
          <DownloadDocxButton workflowRunId={results?.workflowRunId} results={results} />
          <AnalysisOptionsMenu
            onSaveAsEvalTest={handleSaveAsEvalTest}
            onReevaluate={() => setIsReevaluationDialogOpen(true)}
          />
        </div>
      </div>

      <Card>
        <CardContent className={activeTab === 'document-explorer' ? 'h-[calc(100vh-17.5rem)]' : ''}>
          {renderActiveTab()}
        </CardContent>
      </Card>

      <Dialog open={isReevaluationDialogOpen} onOpenChange={setIsReevaluationDialogOpen}>
        <ReevaluationDialogContent
          isPending={false}
          onCancel={() => setIsReevaluationDialogOpen(false)}
          onConfirm={handleReevaluate}
        />
      </Dialog>
    </div>
  );
}
