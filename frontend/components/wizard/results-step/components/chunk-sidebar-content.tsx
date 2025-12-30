import { AiGeneratedLabel } from '@/components/ai-generated-label';
import { Badge } from '@/components/ui/badge';
import type { DocumentIssue, WorkflowRunDetail } from '@/lib/generated-api';
import { WorkflowRunType } from '@/lib/generated-api';
import { getClaimIssues, getMaxSeverity, sortBySeverity } from '@/lib/severity';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { X } from 'lucide-react';
import { useMemo } from 'react';
import { ChunkAnalysisCard } from './chunk-analysis-card';
import { ChunkStatusBadge, useShouldShowStatusBadge } from './chunk-status-badge';
import { ClaimAnalysisCard } from './claim-analysis-card';
import { ErrorsCard } from './errors-card';

export interface ChunkSidebarContentProps {
  chunkIndex: number;
  projectId: string;
  isWorkflowRunning: boolean;
  onClearChunkSelection: () => void;
  allWorkflowDetails: WorkflowRunDetail[];
  issues: DocumentIssue[];
  readOnly?: boolean;
}

export function ChunkSidebarContent({
  chunkIndex,
  projectId,
  isWorkflowRunning,
  onClearChunkSelection,
  allWorkflowDetails,
  issues,
  readOnly = false,
}: ChunkSidebarContentProps) {
  // Extract claim substantiation workflow detail from all workflow details
  const claimSubstantiatorDetail = useMemo(
    () => getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ClaimSubstantiation),
    [allWorkflowDetails],
  );

  const results = claimSubstantiatorDetail?.state;
  const workflowRunId = claimSubstantiatorDetail?.run.id;
  const shouldShowStatusBadge = useShouldShowStatusBadge(isWorkflowRunning);

  if (!results) {
    return null;
  }

  const chunkErrors = results.errors?.filter((error) => error.chunk_index === chunkIndex) ?? [];
  const chunkDetails = results.chunks?.find((chunk) => chunk.chunk_index === chunkIndex);

  if (!chunkDetails) {
    return null;
  }
  const claims = chunkDetails?.claims?.claims ?? [];
  const sortedClaimsBySeverity = claims
    .map((claim, originalIndex) => ({ claim, originalIndex }))
    .sort((a, b) => {
      const aIssues = getClaimIssues(issues, chunkIndex, a.originalIndex);
      const bIssues = getClaimIssues(issues, chunkIndex, b.originalIndex);
      const aMaxSeverity = getMaxSeverity(aIssues);
      const bMaxSeverity = getMaxSeverity(bIssues);
      return sortBySeverity(aMaxSeverity, bMaxSeverity);
    });

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        {shouldShowStatusBadge && <ChunkStatusBadge chunk={chunkDetails} isWorkflowRunning={isWorkflowRunning} />}

        <Badge variant="secondary" className="gap-1 pl-2.5 pr-1">
          Chunk #{chunkDetails.chunk_index}
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

      {sortedClaimsBySeverity.map(({ claim, originalIndex }) => (
        <ClaimAnalysisCard
          key={originalIndex}
          results={results}
          claim={claim}
          chunkDetails={chunkDetails}
          chunkIndex={chunkIndex}
          claimIndex={originalIndex}
          totalClaims={claims.length}
          workflowRunId={workflowRunId || ''}
          allWorkflowDetails={allWorkflowDetails}
          issues={issues}
          readOnly={readOnly}
        />
      ))}

      <ChunkAnalysisCard results={results} chunk={chunkDetails} issues={issues} />
    </div>
  );
}
