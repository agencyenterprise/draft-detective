import type { ProjectDetailed, WorkflowRunDetail } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { getChunkErrors } from '@/lib/workflow-state';
import { useMemo } from 'react';
import { getChunkClaims, useChunkWorkflowData } from '../hooks/use-chunk-workflow-data';
import { ChunkAnalysisCard } from './chunk-analysis-card';
import { ClaimAnalysisCard } from './claim-analysis-card';
import { ErrorsCard } from './errors-card';

export interface SingleChunkContentProps {
  chunkIndex: number;
  projectDetail: ProjectDetailed;
  workflowRuns: WorkflowRunDetail[];
  readOnly: boolean;
  showChunkLabel: boolean;
}

export function SingleChunkContent({
  chunkIndex,
  projectDetail,
  workflowRuns,
  readOnly,
  showChunkLabel,
}: SingleChunkContentProps) {
  const chunkErrors = getChunkErrors(workflowRuns, chunkIndex);

  const { claimExtractionState } = useChunkWorkflowData(workflowRuns);

  const claims = useMemo(() => getChunkClaims(chunkIndex, claimExtractionState), [chunkIndex, claimExtractionState]);

  return (
    <div className={cn('space-y-2', showChunkLabel ? 'border-t pt-3 mt-3 first:border-t-0 first:pt-0 first:mt-0' : '')}>
      {showChunkLabel && (
        <div className="text-xs font-semibold text-muted-foreground mb-2 bg-muted/50 px-2 py-1 rounded">
          Chunk #{chunkIndex}
        </div>
      )}

      {chunkErrors.length > 0 && <ErrorsCard errors={chunkErrors} />}

      {claims.map(({ claim, originalIndex }) => (
        <ClaimAnalysisCard
          key={`${chunkIndex}-${originalIndex}`}
          claim={claim}
          chunkIndex={chunkIndex}
          claimIndex={originalIndex}
          totalClaims={claims.length}
          projectDetail={projectDetail}
          readOnly={readOnly}
        />
      ))}

      <ChunkAnalysisCard chunkIndex={chunkIndex} projectDetail={projectDetail} />
    </div>
  );
}
