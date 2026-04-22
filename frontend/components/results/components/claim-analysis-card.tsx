'use client';

import { ClaimFeedback } from '@/components/claim-feedback';
import { LabeledValue } from '@/components/labeled-value';
import { getClaimId } from '@/lib/chunk-ids';
import { composeReferences } from '@/lib/composed-references';
import { Claim, ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { useMemo } from 'react';
import { AnalysisResultCard } from './analysis-result-card';
import { ClaimArgumentAnalysis } from './claim-argument-analysis';
import { ClaimCategoryResults } from './claim-category-results';
import { ClaimCitationSuggestions } from './claim-citation-suggestions';
import { ClaimLiveReports } from './claim-live-reports';
import { SubstantiationResults } from './substantiation-results';

export interface ClaimAnalysisCardProps {
  claim: Claim;
  claimIndex: number;
  totalClaims: number;
  chunkIndex: number;
  projectDetail: ProjectDetailed;
  readOnly?: boolean;
}

export function ClaimAnalysisCard({
  claim,
  claimIndex,
  totalClaims,
  chunkIndex,
  projectDetail,
  readOnly = false,
}: ClaimAnalysisCardProps) {
  const workflowDetails = useMemo(() => projectDetail.workflow_runs ?? [], [projectDetail.workflow_runs]);
  const files = useMemo(() => projectDetail.files ?? [], [projectDetail.files]);

  const documentProcessingDetail = useMemo(
    () => getWorkflowRunByType(workflowDetails, WorkflowRunType.DocumentProcessing),
    [workflowDetails],
  );
  const claimReferenceValidationDetail = useMemo(
    () => getWorkflowRunByType(workflowDetails, WorkflowRunType.ClaimReferenceValidation),
    [workflowDetails],
  );
  const citationSuggesterDetail = useMemo(
    () => getWorkflowRunByType(workflowDetails, WorkflowRunType.CitationSuggester),
    [workflowDetails],
  );
  const liveReportsDetail = useMemo(
    () => getWorkflowRunByType(workflowDetails, WorkflowRunType.LiveReports),
    [workflowDetails],
  );
  const claimExtractionDetail = useMemo(
    () => getWorkflowRunByType(workflowDetails, WorkflowRunType.ClaimExtraction),
    [workflowDetails],
  );
  const referenceExtractionDetail = useMemo(
    () => getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceExtraction),
    [workflowDetails],
  );
  const referenceFileMatchingDetail = useMemo(
    () => getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceFileMatching),
    [workflowDetails],
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
  const supportingFiles = documentProcessingDetail?.state?.supporting_files ?? [];

  // Compose references from extraction and file matching states
  const references = useMemo(
    () =>
      composeReferences(
        referenceExtractionDetail?.state?.extracted_references,
        referenceFileMatchingDetail?.state?.matches,
        files,
      ),
    [referenceExtractionDetail?.state?.extracted_references, referenceFileMatchingDetail?.state?.matches, files],
  );

  return (
    <AnalysisResultCard
      id={getClaimId(chunkIndex, claimIndex)}
      title={`Claim Analysis - ${claimIndex + 1} of ${totalClaims}`}
    >
      <p className="italic text-center">&quot;{claim.text}&quot;</p>

      <div className="space-y-1">
        <LabeledValue label="Extracted Claim">{claim.claim}</LabeledValue>
        {'central' in claim && (
          <>
            <LabeledValue label="Central Claim">{claim.central ? 'Yes' : 'No'}</LabeledValue>
            <LabeledValue label="Centrality Rationale">{claim.centrality_rationale}</LabeledValue>
          </>
        )}
      </div>

      <div className="space-y-2">
        <ClaimArgumentAnalysis claim={claim} />
        {claimCategory && <ClaimCategoryResults claimCategory={claimCategory} />}
        {substantiation && (
          <SubstantiationResults
            substantiation={substantiation}
            references={references}
            supportingFiles={supportingFiles}
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
      </div>

      {!readOnly && documentProcessingDetail?.run.id && chunkIndex !== undefined && (
        <ClaimFeedback
          workflowRunId={documentProcessingDetail?.run.id}
          chunkIndex={chunkIndex}
          claimIndex={claimIndex}
        />
      )}
    </AnalysisResultCard>
  );
}
