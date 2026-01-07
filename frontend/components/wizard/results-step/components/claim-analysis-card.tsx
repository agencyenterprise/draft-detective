'use client';

import { ClaimFeedback } from '@/components/claim-feedback';
import { LabeledValue } from '@/components/labeled-value';
import { Button } from '@/components/ui/button';
import { getClaimId } from '@/lib/chunk-ids';
import { Claim, DocumentIssue, WorkflowRunDetail, WorkflowRunType } from '@/lib/generated-api';
import { getClaimIssues, getMaxSeverity } from '@/lib/severity';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { ChevronDownIcon, ChevronRightIcon } from 'lucide-react';
import { useMemo, useState } from 'react';
import { AnalysisResultCard } from './analysis-result-card';
import { ClaimArgumentAnalysis } from './claim-argument-analysis';
import { ClaimCategoryResults } from './claim-category-results';
import { ClaimCitationSuggestions } from './claim-citation-suggestions';
import { ClaimInferenceValidation } from './claim-inference-validation';
import { ClaimLiveReports } from './claim-live-reports';
import { DocumentIssueCardMinimal } from './document-issue-card';
import { SubstantiationResults } from './substantiation-results';

export interface ClaimAnalysisCardProps {
  claim: Claim;
  claimIndex: number;
  totalClaims: number;
  chunkIndex: number;
  allWorkflowDetails: WorkflowRunDetail[];
  issues: DocumentIssue[];
  readOnly?: boolean;
}

export function ClaimAnalysisCard({
  claim,
  claimIndex,
  totalClaims,
  chunkIndex,
  allWorkflowDetails,
  issues,
  readOnly = false,
}: ClaimAnalysisCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const documentProcessingDetail = useMemo(
    () => getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.DocumentProcessing),
    [allWorkflowDetails],
  );
  const claimReferenceValidationDetail = useMemo(
    () => getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ClaimReferenceValidation),
    [allWorkflowDetails],
  );
  const citationSuggesterDetail = useMemo(
    () => getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.CitationSuggester),
    [allWorkflowDetails],
  );
  const liveReportsDetail = useMemo(
    () => getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.LiveReports),
    [allWorkflowDetails],
  );
  const inferenceValidationDetail = useMemo(
    () => getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.InferenceValidation),
    [allWorkflowDetails],
  );
  const claimExtractionDetail = useMemo(
    () => getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ClaimExtraction),
    [allWorkflowDetails],
  );
  const referenceExtractionDetail = useMemo(
    () => getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ReferenceExtraction),
    [allWorkflowDetails],
  );

  const claimCategory = claimExtractionDetail?.state?.claim_categories?.find(
    (c) => c.chunk_index === chunkIndex && c.claim_index === claimIndex,
  );
  const substantiation = claimReferenceValidationDetail?.state?.substantiations?.find(
    (s) => s.chunk_index === chunkIndex && s.claim_index === claimIndex,
  );
  const citationSuggestion = citationSuggesterDetail?.state?.citation_suggestions?.find(
    (c) => c.chunk_index === chunkIndex && c.claim_index === claimIndex,
  );
  const liveReportsAnalysis = liveReportsDetail?.state?.live_reports_analysis?.find(
    (l) => l.chunk_index === chunkIndex && l.claim_index === claimIndex,
  );
  const inferenceValidation = inferenceValidationDetail?.state?.inference_validations?.find(
    (i) => i.chunk_index === chunkIndex && i.claim_index === claimIndex,
  );

  const supportingFiles = documentProcessingDetail?.state?.supporting_files ?? [];
  const references = referenceExtractionDetail?.state?.references ?? [];
  const claimIssues = getClaimIssues(issues, chunkIndex, claimIndex);
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
          {'central' in claim && <LabeledValue label="Central Claim">{claim.central ? 'Yes' : 'No'}</LabeledValue>}

          <div className="space-y-2">
            <ClaimArgumentAnalysis claim={claim} />
            {claimCategory && <ClaimCategoryResults claimCategory={claimCategory} />}
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

          {!readOnly && documentProcessingDetail?.run.id && chunkIndex !== undefined && (
            <ClaimFeedback
              workflowRunId={documentProcessingDetail?.run.id}
              chunkIndex={chunkIndex}
              claimIndex={claimIndex}
            />
          )}
        </>
      )}
    </AnalysisResultCard>
  );
}
