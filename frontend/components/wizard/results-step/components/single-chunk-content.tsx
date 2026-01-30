import { Button } from '@/components/ui/button';
import type { ProjectDetailed, WorkflowRunDetail } from '@/lib/generated-api';
import { getClaimIssues, getMaxSeverity, sortBySeverity } from '@/lib/severity';
import { getChunkErrors } from '@/lib/workflow-state';
import { ExternalLink } from 'lucide-react';
import { useMemo } from 'react';
import {
  findReferenceForChunk,
  getChunkClaims,
  useChunkWorkflowData,
  type MatchedReference,
} from '../hooks/use-chunk-workflow-data';
import { ValidationResultsBox } from '../tabs/reference-review/validation-results-box';
import { ChunkAnalysisCard } from './chunk-analysis-card';
import { ClaimAnalysisCard } from './claim-analysis-card';
import { ErrorsCard } from './errors-card';
import { cn } from '@/lib/utils';

export interface SingleChunkContentProps {
  chunkIndex: number;
  projectDetail: ProjectDetailed;
  workflowRuns: WorkflowRunDetail[];
  readOnly: boolean;
  onNavigateToReferences?: (referenceIndex: number) => void;
  showChunkLabel: boolean;
}

export function SingleChunkContent({
  chunkIndex,
  projectDetail,
  workflowRuns,
  readOnly,
  onNavigateToReferences,
  showChunkLabel,
}: SingleChunkContentProps) {
  const issues = useMemo(() => projectDetail.issues ?? [], [projectDetail.issues]);
  const chunkErrors = getChunkErrors(workflowRuns, chunkIndex);

  const { claimExtractionState, referenceExtractionState, referenceValidationState } =
    useChunkWorkflowData(workflowRuns);

  const claims = useMemo(() => getChunkClaims(chunkIndex, claimExtractionState), [chunkIndex, claimExtractionState]);

  const sortedClaimsBySeverity = useMemo(
    () =>
      claims.sort((a, b) => {
        const aIssues = getClaimIssues(issues, chunkIndex, a.originalIndex);
        const bIssues = getClaimIssues(issues, chunkIndex, b.originalIndex);
        return sortBySeverity(getMaxSeverity(aIssues), getMaxSeverity(bIssues));
      }),
    [claims, issues, chunkIndex],
  );

  const matchedReference = useMemo(
    () => findReferenceForChunk(chunkIndex, referenceExtractionState, referenceValidationState),
    [chunkIndex, referenceExtractionState, referenceValidationState],
  );

  return (
    <div className={cn('space-y-2', showChunkLabel ? 'border-t pt-3 mt-3 first:border-t-0 first:pt-0 first:mt-0' : '')}>
      {showChunkLabel && (
        <div className="text-xs font-semibold text-muted-foreground mb-2 bg-muted/50 px-2 py-1 rounded">
          Chunk #{chunkIndex}
        </div>
      )}

      {chunkErrors.length > 0 && <ErrorsCard errors={chunkErrors} />}

      {sortedClaimsBySeverity.map(({ claim, originalIndex }) => (
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

      {matchedReference && (
        <ReferenceSection
          referenceIndex={matchedReference.index}
          validation={matchedReference.validation}
          onNavigateToReferences={onNavigateToReferences}
        />
      )}
    </div>
  );
}

interface ReferenceSectionProps {
  referenceIndex: number;
  validation: MatchedReference['validation'];
  onNavigateToReferences?: (referenceIndex: number) => void;
}

function ReferenceSection({ referenceIndex, validation, onNavigateToReferences }: ReferenceSectionProps) {
  return (
    <div className="space-y-2 pt-2 border-t">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">Reference #{referenceIndex + 1}</span>
        {onNavigateToReferences && (
          <Button
            variant="ghost"
            size="xs"
            onClick={() => onNavigateToReferences(referenceIndex)}
            className="text-xs gap-1"
          >
            <ExternalLink className="h-3 w-3" />
            View in References
          </Button>
        )}
      </div>
      {validation && <ValidationResultsBox validation={validation} />}
    </div>
  );
}
