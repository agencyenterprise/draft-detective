'use client';

import { analysisService } from '@/lib/analysis-service';
import { downloadFile, generateEvalFilename } from '@/lib/file-download';
import { ChunkReevaluationResponse, ClaimSubstantiatorStateSummary } from '@/lib/generated-api';
import { DocRenderMode } from '@/lib/constants';
import { FileText } from 'lucide-react';
import * as React from 'react';
import { Button } from '../../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../ui/card';
import { Tooltip, TooltipContent, TooltipTrigger } from '../../ui/tooltip';
import { TabNavigation } from './components';
import { TabType } from './constants';
import { useResultsCalculations } from './hooks/use-results-calculations';
import { CitationsTab, FilesTab, LiteratureReviewTab, LiveReportsTab, ReferencesTab, SummaryTab } from './tabs';
import { DocumentExplorerTab } from './tabs/document-explorer-tab';

interface ResultsVisualizationProps {
  results: ClaimSubstantiatorStateSummary | undefined;
  onChunkReevaluation: (response: ChunkReevaluationResponse) => void;
  isProcessing?: boolean;
  viewMode?: DocRenderMode;
  activeTab?: TabType;
  onTabChange?: (tab: TabType) => void;
}

export function ResultsVisualization({
  results,
  onChunkReevaluation,
  isProcessing = false,
  viewMode,
  activeTab: activeTabProp,
  onTabChange: onTabChangeProp,
}: ResultsVisualizationProps) {
  const [localActiveTab, setLocalActiveTab] = React.useState<TabType>('document-explorer');
  const activeTab = activeTabProp ?? localActiveTab;
  const setActiveTab = onTabChangeProp ?? setLocalActiveTab;

  const calculations = useResultsCalculations(results);

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
      case 'citations':
        return <CitationsTab results={results} isProcessing={isProcessing} />;
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
            results={results}
            onChunkReevaluation={onChunkReevaluation}
            isProcessing={isProcessing}
            viewMode={viewMode}
          />
        );
    }
  };

  return (
    <div className="space-y-6">
      <TabNavigation activeTab={activeTab} onTabChange={setActiveTab} />

      <Card>
        <CardContent className={activeTab === 'document-explorer' ? 'p-3 h-[calc(100vh-16rem)]' : 'p-3'}>
          {renderActiveTab()}
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button onClick={handleSaveAsEvalTest} variant="outline" size="sm" className="gap-2">
              <FileText className="h-4 w-4" />
              Save all as Eval Test
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>Generate evaluation test cases from these results for testing agents</p>
          </TooltipContent>
        </Tooltip>
      </div>
    </div>
  );
}
