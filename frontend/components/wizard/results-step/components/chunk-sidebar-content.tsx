import { AiGeneratedLabel } from '@/components/ai-generated-label';
import { Badge } from '@/components/ui/badge';
import type { ProjectDetailed } from '@/lib/generated-api';
import { WorkflowRunType } from '@/lib/generated-api';
import { getClaimIssues, getMaxSeverity, sortBySeverity } from '@/lib/severity';
import { getChunkErrors, getWorkflowRunByType } from '@/lib/workflow-state';
import { X } from 'lucide-react';
import { useMemo } from 'react';
import { ChunkAnalysisCard } from './chunk-analysis-card';
import { ClaimAnalysisCard } from './claim-analysis-card';
import { ErrorsCard } from './errors-card';

export interface ChunkSidebarContentProps {
  chunkIndex: number;
  projectDetail: ProjectDetailed;
  readOnly?: boolean;
  onClearChunkSelection: () => void;
}

export function ChunkSidebarContent({
  chunkIndex,
  projectDetail,
  readOnly = false,
  onClearChunkSelection,
}: ChunkSidebarContentProps) {
  const workflowDetails = useMemo(() => projectDetail.workflow_runs ?? [], [projectDetail.workflow_runs]);
  const issues = useMemo(() => projectDetail.issues ?? [], [projectDetail.issues]);

  const claimExtractionDetail = useMemo(
    () => getWorkflowRunByType(workflowDetails, WorkflowRunType.ClaimExtraction),
    [workflowDetails],
  );

  const chunkErrors = getChunkErrors(workflowDetails, chunkIndex);

  const claims =
    claimExtractionDetail?.state?.claims?.filter((c) => c.chunk_index === chunkIndex).flatMap((c) => c.claims) ?? [];

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
        <Badge variant="secondary" className="gap-1 pl-2.5 pr-1">
          Chunk #{chunkIndex}
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
