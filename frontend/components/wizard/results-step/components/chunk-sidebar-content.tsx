import { AiGeneratedLabel } from '@/components/ai-generated-label';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { BibliographyItemValidation, ProjectDetailed } from '@/lib/generated-api';
import { WorkflowRunType } from '@/lib/generated-api';
import { getClaimIssues, getMaxSeverity, sortBySeverity } from '@/lib/severity';
import { getChunkErrors, getWorkflowRunByType } from '@/lib/workflow-state';
import { ExternalLink, X } from 'lucide-react';
import { useMemo } from 'react';
import { ValidationResultsBox } from '../tabs/reference-review/validation-results-box';
import { ChunkAnalysisCard } from './chunk-analysis-card';
import { ClaimAnalysisCard } from './claim-analysis-card';
import { ErrorsCard } from './errors-card';

export interface ChunkSidebarContentProps {
  chunkIndex: number;
  projectDetail: ProjectDetailed;
  readOnly?: boolean;
  onClearChunkSelection: () => void;
  onNavigateToReferences?: (referenceIndex: number) => void;
}

interface MatchedReference {
  index: number;
  validation: BibliographyItemValidation | null;
}

export function ChunkSidebarContent({
  chunkIndex,
  projectDetail,
  readOnly = false,
  onClearChunkSelection,
  onNavigateToReferences,
}: ChunkSidebarContentProps) {
  const workflowDetails = projectDetail.workflow_runs ?? [];
  const issues = projectDetail.issues ?? [];

  const { claimExtraction, documentProcessing, referenceExtraction, referenceValidation } = useMemo(
    () => ({
      claimExtraction: getWorkflowRunByType(workflowDetails, WorkflowRunType.ClaimExtraction),
      documentProcessing: getWorkflowRunByType(workflowDetails, WorkflowRunType.DocumentProcessing),
      referenceExtraction: getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceExtraction),
      referenceValidation: getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceValidation),
    }),
    [workflowDetails],
  );

  const chunkErrors = getChunkErrors(workflowDetails, chunkIndex);

  const claims =
    claimExtraction?.state?.claims?.filter((c) => c.chunk_index === chunkIndex).flatMap((c) => c.claims) ?? [];

  const sortedClaimsBySeverity = claims
    .map((claim, originalIndex) => ({ claim, originalIndex }))
    .sort((a, b) => {
      const aIssues = getClaimIssues(issues, chunkIndex, a.originalIndex);
      const bIssues = getClaimIssues(issues, chunkIndex, b.originalIndex);
      const aMaxSeverity = getMaxSeverity(aIssues);
      const bMaxSeverity = getMaxSeverity(bIssues);
      return sortBySeverity(aMaxSeverity, bMaxSeverity);
    });

  // Find if this chunk is a reference by matching chunk content with extracted references
  const matchedReference = useMemo((): MatchedReference | null => {
    const chunks = documentProcessing?.state?.chunks ?? [];
    const chunk = chunks.find((c) => c.chunk_index === chunkIndex);
    if (!chunk) return null;

    const extractedRefs = referenceExtraction?.state?.extracted_references ?? [];
    const validations = referenceValidation?.state?.reference_validations ?? [];

    // Find reference that contains or matches this chunk's content
    const chunkContent = chunk.content.trim().toLowerCase();
    const refIndex = extractedRefs.findIndex((ref) => {
      const refText = ref.text.trim().toLowerCase();
      // Check if chunk content is part of reference or vice versa
      return refText.includes(chunkContent) || chunkContent.includes(refText);
    });

    if (refIndex === -1) return null;

    const ref = extractedRefs[refIndex];
    const validation = validations.find((v) => v.original_reference === ref.text) ?? null;

    return { index: refIndex, validation };
  }, [documentProcessing, referenceExtraction, referenceValidation, chunkIndex]);

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

      {/* Reference Validation Section */}
      {matchedReference && (
        <div className="space-y-2 pt-2 border-t">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">Reference #{matchedReference.index + 1}</span>
            {onNavigateToReferences && (
              <Button
                variant="ghost"
                size="xs"
                onClick={() => onNavigateToReferences(matchedReference.index)}
                className="text-xs gap-1"
              >
                <ExternalLink className="h-3 w-3" />
                View in References
              </Button>
            )}
          </div>
          {matchedReference.validation && <ValidationResultsBox validation={matchedReference.validation} />}
        </div>
      )}
    </div>
  );
}
