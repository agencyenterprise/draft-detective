'use client';

import { ClaimFeedback } from '@/components/claim-feedback';
import { LabeledValue } from '@/components/labeled-value';
import { Button } from '@/components/ui/button';
import { ClaimSubstantiatorStateSummary, DocumentChunkOutput, ToulminClaim } from '@/lib/generated-api';
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
  claim: ToulminClaim;
  chunkDetails: DocumentChunkOutput | undefined | null;
  claimIndex: number;
  totalClaims: number;
  chunkIndex: number;
}

export function ClaimAnalysisCard({
  results,
  claim,
  chunkDetails,
  claimIndex,
  totalClaims,
  chunkIndex,
}: ClaimAnalysisCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!chunkDetails) {
    return null;
  }

  const claimCategory = chunkDetails.claimCategories?.find((c) => c.claimIndex === claimIndex);
  const commonKnowledgeResult = chunkDetails.claimCommonKnowledgeResults?.find((c) => c.claimIndex === claimIndex);
  const substantiation = chunkDetails.substantiations?.find((s) => s.claimIndex === claimIndex);
  const citationSuggestion = chunkDetails.citationSuggestions?.find((c) => c.claimIndex === claimIndex);
  const liveReportsAnalysis = chunkDetails.liveReportsAnalysis?.find((l) => l.claimIndex === claimIndex);
  const inferenceValidation = chunkDetails.inferenceValidations?.find((i) => i.claimIndex === claimIndex);

  const workflowRunId = results.workflowRunId;
  const supportingFiles = results.supportingFiles ?? [];
  const references = results.references ?? [];
  const claimIssues = getClaimIssues(results, chunkIndex, claimIndex);
  const maxSeverity = getMaxSeverity(claimIssues);

  return (
    <AnalysisResultCard title={`Claim Analysis - ${claimIndex + 1} of ${totalClaims}`} severity={maxSeverity}>
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
                retrievedPassages={substantiation.retrievedPassages ?? undefined}
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

          {workflowRunId && chunkIndex !== undefined && (
            <ClaimFeedback workflowRunId={workflowRunId} chunkIndex={chunkIndex} claimIndex={claimIndex} />
          )}
        </>
      )}
    </AnalysisResultCard>
  );
}
