'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { CitationSuggesterState, CitationSuggestionResultWithClaimIndex, WorkflowRunDetail } from '@/lib/generated-api';
import { AlertCircle, Link2Icon } from 'lucide-react';
import * as React from 'react';
import { ClaimCitationSuggestions } from '../../wizard/results-step/components/claim-citation-suggestions';

interface CitationSuggesterResultsProps {
  workflowDetail: WorkflowRunDetail;
}

export function CitationSuggesterResults({ workflowDetail }: CitationSuggesterResultsProps) {
  const results = workflowDetail.state as CitationSuggesterState | undefined;

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
}
