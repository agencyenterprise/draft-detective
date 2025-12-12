import { AiGeneratedLabel } from '@/components/ai-generated-label';
import { Badge } from '@/components/ui/badge';
import type { ClaimSubstantiatorStateSummary, DocumentIssue } from '@/lib/generated-api';
import { useChunkDetails } from '@/lib/hooks/use-chunk-details';
import { getClaimIssues, getMaxSeverity, sortBySeverity } from '@/lib/severity';
import { Loader2, X } from 'lucide-react';
import { ChunkAnalysisCard } from './chunk-analysis-card';
import { ChunkEvalGenerator } from './chunk-eval-generator';
import { ChunkReevaluateControl } from './chunk-reevaluate-control';
import { ChunkStatusBadge, useShouldShowStatusBadge } from './chunk-status-badge';
import { ClaimAnalysisCard } from './claim-analysis-card';
import { ErrorsCard } from './errors-card';

export interface ChunkSidebarContentProps {
  results: ClaimSubstantiatorStateSummary;
  chunkIndex: number;
  projectId: string;
  workflowRunId: string;
  isWorkflowRunning: boolean;
  onSelectIssue: (issue: DocumentIssue) => void;
  onClearChunkSelection: () => void;
  readOnly?: boolean;
}

export function ChunkSidebarContent({
  results,
  chunkIndex,
  projectId,
  workflowRunId,
  isWorkflowRunning,
  onSelectIssue,
  onClearChunkSelection,
  readOnly = false,
}: ChunkSidebarContentProps) {
  const { data: chunkDetails, isLoading: isLoadingDetails } = useChunkDetails(
    workflowRunId || '',
    chunkIndex,
    !!workflowRunId,
    isWorkflowRunning,
  );

  const chunkErrors = results.errors?.filter((error) => error.chunk_index === chunkIndex) ?? [];
  const lightweightChunk = results.chunks?.find((chunk) => chunk.chunk_index === chunkIndex);
  const shouldShowStatusBadge = useShouldShowStatusBadge(isWorkflowRunning);

  const claims = chunkDetails?.claims?.claims ?? [];
  const sortedClaimsBySeverity = claims
    .map((claim, originalIndex) => ({ claim, originalIndex }))
    .sort((a, b) => {
      const aIssues = getClaimIssues(results, chunkIndex, a.originalIndex);
      const bIssues = getClaimIssues(results, chunkIndex, b.originalIndex);
      const aMaxSeverity = getMaxSeverity(aIssues);
      const bMaxSeverity = getMaxSeverity(bIssues);
      return sortBySeverity(aMaxSeverity, bMaxSeverity);
    });

  if (!lightweightChunk) {
    return null;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        {shouldShowStatusBadge && chunkDetails && (
          <ChunkStatusBadge chunk={chunkDetails} isWorkflowRunning={isWorkflowRunning} />
        )}

        <Badge variant="secondary" className="gap-1 pl-2.5 pr-1">
          Chunk #{lightweightChunk.chunk_index}
          <button
            onClick={onClearChunkSelection}
            className="ml-0.5 rounded-sm hover:bg-muted-foreground/20 p-0.5"
            aria-label="Clear chunk selection"
          >
            <X className="h-3 w-3" />
          </button>
        </Badge>

        <AiGeneratedLabel className="ml-auto" />
      </div>

      {chunkErrors.length > 0 && <ErrorsCard errors={chunkErrors} />}

      {isLoadingDetails && (
        <div className="flex items-center justify-center py-8">
          <div className="text-center space-y-3">
            <Loader2 className="h-6 w-6 animate-spin text-primary mx-auto" />
            <p className="text-sm text-muted-foreground">Loading detailed analysis...</p>
          </div>
        </div>
      )}

      {!isLoadingDetails && (
        <>
          {sortedClaimsBySeverity.map(({ claim, originalIndex }) => (
            <ClaimAnalysisCard
              key={originalIndex}
              results={results}
              claim={claim}
              chunkDetails={chunkDetails}
              chunkIndex={chunkIndex}
              claimIndex={originalIndex}
              totalClaims={claims.length}
              workflowRunId={workflowRunId}
              readOnly={readOnly}
            />
          ))}

          {chunkDetails && <ChunkAnalysisCard results={results} chunk={chunkDetails} />}

          {!readOnly && (
            <>
              <ChunkReevaluateControl
                results={results}
                chunkIndex={lightweightChunk.chunk_index}
                projectId={projectId}
              />

              <ChunkEvalGenerator chunkIndex={lightweightChunk.chunk_index} originalState={results} />
            </>
          )}
        </>
      )}
    </div>
  );
}
