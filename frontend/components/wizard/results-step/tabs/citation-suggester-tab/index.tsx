'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { StartWorkflowButton } from '@/components/workflows/start-workflow-button';
import { WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import {
  CitationSuggesterState,
  CitationSuggestionResultWithClaimIndex,
  startWorkflowApiWorkflowsStartPost,
  WorkflowRunStatus,
  WorkflowRunType,
} from '@/lib/generated-api';
import { WorkflowRunDetailTyped } from '@/lib/workflow-state';
import { AlertCircle, Link2Icon } from 'lucide-react';
import * as React from 'react';
import { TabWithLoadingStates } from '../tab-with-loading-states';
import { ClaimCitationSuggestions } from '../../components/claim-citation-suggestions';

interface CitationSuggesterTabProps {
  workflowDetail: WorkflowRunDetailTyped<CitationSuggesterState> | undefined;
  projectId: string;
  readOnly?: boolean;
}

export function CitationSuggesterTab({ workflowDetail, projectId, readOnly = false }: CitationSuggesterTabProps) {
  const results = workflowDetail?.state;
  const runStatus = workflowDetail?.run.status;

  const handleStartWorkflow = async (values: WorkflowConfigFormValues) => {
    return await startWorkflowApiWorkflowsStartPost({
      body: {
        type: WorkflowRunType.CitationSuggester,
        project_id: projectId,
        openai_api_key: values.openaiApiKey || null,
      },
    });
  };

  const citationSuggestions = React.useMemo(() => results?.citation_suggestions ?? [], [results?.citation_suggestions]);
  const references = results?.references ?? [];
  const supportingFiles = results?.supporting_files ?? [];

  // Group suggestions by chunk_index and claim_index
  const groupedSuggestions = React.useMemo(() => {
    const grouped: Record<number, Record<number, CitationSuggestionResultWithClaimIndex[]>> = {};
    citationSuggestions.forEach((suggestion) => {
      if (!grouped[suggestion.chunk_index]) {
        grouped[suggestion.chunk_index] = {};
      }
      if (!grouped[suggestion.chunk_index][suggestion.claim_index]) {
        grouped[suggestion.chunk_index][suggestion.claim_index] = [];
      }
      grouped[suggestion.chunk_index][suggestion.claim_index].push(suggestion);
    });
    return grouped;
  }, [citationSuggestions]);

  const totalSuggestions = citationSuggestions.length;
  const totalReferences = citationSuggestions.reduce(
    (sum, suggestion) => sum + (suggestion.relevant_references?.length ?? 0),
    0,
  );

  return (
    <>
      <TabWithLoadingStates
        title="Citation Suggester"
        data={citationSuggestions.length > 0 ? citationSuggestions : null}
        isProcessing={runStatus === WorkflowRunStatus.Running}
        hasData={(suggestions) => suggestions !== null && suggestions !== undefined && suggestions.length > 0}
        loadingMessage={{
          title: 'Generating citation suggestions...',
          description: 'This may take some minutes as we analyze claims and suggest relevant citations',
        }}
        emptyMessage={{
          icon: <AlertCircle className="h-12 w-12 text-muted-foreground" />,
          title: 'No citation suggestions available',
          description: 'Run the citation suggester to generate recommendations for adding citations to claims.',
        }}
        emptyStateChildren={
          <div className="text-sm text-muted-foreground text-left max-w-md space-y-3">
            <div>
              <p className="mb-2 font-medium">Why run this?</p>
              <ul className="list-disc pl-5 space-y-1">
                <li>Get suggestions for citations to add to unsupported claims</li>
                <li>Identify references from bibliography that should be cited</li>
                <li>Find new references from literature review to support claims</li>
              </ul>
            </div>
          </div>
        }
        skeletonType="paragraphs"
        skeletonCount={6}
        triggerButton={
          !readOnly && (
            <StartWorkflowButton
              type={WorkflowRunType.CitationSuggester}
              projectId={projectId}
              workflow={workflowDetail?.run}
              onConfirm={handleStartWorkflow}
            />
          )
        }
      >
        {() => {
          if (totalSuggestions === 0) {
            return (
              <Card>
                <CardContent className="flex items-center justify-center py-12">
                  <div className="text-center space-y-2">
                    <AlertCircle className="h-8 w-8 text-muted-foreground mx-auto" />
                    <p className="text-sm text-muted-foreground">No citation suggestions found.</p>
                  </div>
                </CardContent>
              </Card>
            );
          }

          return (
            <div className="space-y-6">
              <div className="flex items-center gap-2">
                <Link2Icon className="h-5 w-5 text-blue-600" />
                <span className="text-sm font-medium">AI-Generated Citation Suggestions</span>
                <Badge variant="secondary" className="ml-auto">
                  {totalSuggestions} Suggestion{totalSuggestions !== 1 ? 's' : ''}
                </Badge>
                {totalReferences > 0 && (
                  <Badge variant="outline">
                    {totalReferences} Reference{totalReferences !== 1 ? 's' : ''}
                  </Badge>
                )}
              </div>

              <div className="space-y-6">
                {Object.entries(groupedSuggestions)
                  .sort(([a], [b]) => parseInt(a) - parseInt(b))
                  .map(([chunkIndexStr, claimSuggestions]) => {
                    const chunkIndex = parseInt(chunkIndexStr);
                    return (
                      <Card key={chunkIndex}>
                        <CardHeader>
                          <CardTitle className="text-base">Chunk {chunkIndex}</CardTitle>
                          <CardDescription>Citation suggestions for claims in this chunk</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                          {Object.entries(claimSuggestions)
                            .sort(([a], [b]) => parseInt(a) - parseInt(b))
                            .map(([claimIndexStr, suggestions]) => {
                              const claimIndex = parseInt(claimIndexStr);
                              // Use the first suggestion for display (they should all be similar for the same claim)
                              const suggestion = suggestions[0];
                              return (
                                <div key={claimIndex} className="border-t pt-4 first:border-t-0 first:pt-0">
                                  <h4 className="font-medium mb-2">Claim {claimIndex}</h4>
                                  <ClaimCitationSuggestions
                                    citationSuggestion={suggestion}
                                    references={references}
                                    supportingFiles={supportingFiles}
                                  />
                                </div>
                              );
                            })}
                        </CardContent>
                      </Card>
                    );
                  })}
              </div>
            </div>
          );
        }}
      </TabWithLoadingStates>
    </>
  );
}
