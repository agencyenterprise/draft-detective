'use client';

import { ClaimFeedback } from '@/components/claim-feedback';
import { LabeledValue } from '@/components/labeled-value';
import { Button } from '@/components/ui/button';
import { getClaimId } from '@/lib/chunk-ids';
import { Claim, ClaimSubstantiatorStateSummary, DocumentChunkOutput, ToulminClaim } from '@/lib/generated-api';
import { getClaimIssues, getMaxSeverity } from '@/lib/severity';
import { ChevronDownIcon, ChevronRightIcon } from 'lucide-react';
import { useState } from 'react';
import { AnalysisResultCard } from './analysis-result-card';
import { ClaimArgumentAnalysis } from './claim-argument-analysis';
import { ClaimCategoryResults } from './claim-category-results';
import { ClaimCitationSuggestions } from './claim-citation-suggestions';
import { ClaimInferenceValidation } from './claim-inference-validation';
import { ClaimLiveReports } from './claim-live-reports';
import { ClaimNeedsSubstantiationAccordion } from './claim-needs-substantiation-accordion';
import { DocumentIssueCardMinimal } from './document-issue-card';
import { SubstantiationResults } from './substantiation-results';

export interface ClaimAnalysisCardProps {
  results: ClaimSubstantiatorStateSummary;
  claim: Claim | ToulminClaim;
  chunkDetails: DocumentChunkOutput | undefined | null;
  claimIndex: number;
  totalClaims: number;
  chunkIndex: number;
  workflowRunId: string;
  readOnly?: boolean;
}

export function ClaimAnalysisCard({
  results,
  claim,
  chunkDetails,
  claimIndex,
  totalClaims,
  chunkIndex,
  workflowRunId,
  readOnly = false,
}: ClaimAnalysisCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!chunkDetails) {
    return null;
  }

  const claimCategory = chunkDetails.claim_categories?.find((c) => c.claim_index === claimIndex);
  const commonKnowledgeResult = chunkDetails.claim_common_knowledge_results?.find((c) => c.claim_index === claimIndex);
  const substantiation = chunkDetails.substantiations?.find((s) => s.claim_index === claimIndex);
  const citationSuggestion = chunkDetails.citation_suggestions?.find((c) => c.claim_index === claimIndex);
  const liveReportsAnalysis = chunkDetails.live_reports_analysis?.find((l) => l.claim_index === claimIndex);
  const inferenceValidation = chunkDetails.inference_validations?.find((i) => i.claim_index === claimIndex);

  const supportingFiles = results.supporting_files ?? [];
  const references = results.references ?? [];
  const claimIssues = getClaimIssues(results, chunkIndex, claimIndex);
  const maxSeverity = getMaxSeverity(claimIssues);

  return (
    <AnalysisResultCard
      id={getClaimId(chunkIndex, claimIndex)}
      title={`Claim Analysis - ${claimIndex + 1} of ${totalClaims}`}
      severity={maxSeverity}
    >
      <p className="italic text-center">&quot;{claim.text}&quot;</p>

      {!claimIssues.length && <p className="text-muted-foreground">No issues found for this claim.</p>}

      {claimIssues.map((issue, issueIndex) => (
        <DocumentIssueCardMinimal key={issueIndex} issue={issue} />
      ))}

      <div className="flex items-center justify-end">
        <Button variant="ghost" size="xs" onClick={() => setIsExpanded(!isExpanded)}>
          {isExpanded ? <ChevronDownIcon className="size-4" /> : <ChevronRightIcon className="size-4" />}
          {isExpanded ? 'Hide details' : 'Show details'}
        </Button>
      </div>

      {isExpanded && (
        <>
          <LabeledValue label="Extracted Claim">{claim.claim}</LabeledValue>

          <div className="space-y-2">
            <ClaimArgumentAnalysis claim={claim} />
            {claimCategory && <ClaimCategoryResults claimCategory={claimCategory} />}
            {commonKnowledgeResult && <ClaimNeedsSubstantiationAccordion result={commonKnowledgeResult} />}
            {substantiation && (
              <SubstantiationResults
                substantiation={substantiation}
                references={references}
                supportingFiles={supportingFiles}
                retrievedPassages={substantiation.retrieved_passages ?? undefined}
              />
            )}
            {citationSuggestion && (
              <ClaimCitationSuggestions
                citationSuggestion={citationSuggestion}
                references={references}
                supportingFiles={supportingFiles}
              />
            )}
            {liveReportsAnalysis && <ClaimLiveReports liveReportsAnalysis={liveReportsAnalysis} />}
            {inferenceValidation && <ClaimInferenceValidation inferenceValidation={inferenceValidation} />}
          </div>

          {!readOnly && workflowRunId && chunkIndex !== undefined && (
            <ClaimFeedback workflowRunId={workflowRunId} chunkIndex={chunkIndex} claimIndex={claimIndex} />
          )}
        </>
      )}
    </AnalysisResultCard>
  );
}
