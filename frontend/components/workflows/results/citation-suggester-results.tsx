'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/shared';
import { composeReferences } from '@/lib/composed-references';
import { CitationSuggestionResultWithClaimIndex, ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { Link2Icon } from 'lucide-react';
import * as React from 'react';
import { useMemo } from 'react';
import { ClaimCitationSuggestions } from '../../wizard/results-step/components/claim-citation-suggestions';

interface CitationSuggesterResultsProps {
  project: ProjectDetailed;
}

export function CitationSuggesterResults({ project }: CitationSuggesterResultsProps) {
  const files = useMemo(() => project.files ?? [], [project.files]);
  const workflowDetails = useMemo(() => project.workflow_runs ?? [], [project.workflow_runs]);

  const documentProcessing = getWorkflowRunByType(workflowDetails, WorkflowRunType.DocumentProcessing);
  const referenceExtraction = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceExtraction);
  const referenceFileMatching = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceFileMatching);
  const citationSuggester = getWorkflowRunByType(workflowDetails, WorkflowRunType.CitationSuggester);

  const citationSuggestions = useMemo(
    () => citationSuggester?.state?.citation_suggestions ?? [],
    [citationSuggester?.state?.citation_suggestions],
  );
  const supportingFiles = documentProcessing?.state?.supporting_files ?? [];

  // Compose references from extraction and file matching states
  const references = useMemo(
    () =>
      composeReferences(referenceExtraction?.state?.extracted_references, referenceFileMatching?.state?.matches, files),
    [referenceExtraction?.state?.extracted_references, referenceFileMatching?.state?.matches, files],
  );

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

  if (totalSuggestions === 0) {
    return <EmptyState message="No citation suggestions found." />;
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
}
