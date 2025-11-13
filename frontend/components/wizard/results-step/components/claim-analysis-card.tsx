'use client';

import { AiGeneratedLabel } from '@/components/ai-generated-label';
import { ClaimFeedback } from '@/components/claim-feedback';
import { LabeledValue } from '@/components/labeled-value';
import { Card, CardContent } from '@/components/ui/card';
import {
  BibliographyItem,
  CitationSuggestionResultWithClaimIndexOutput,
  ClaimCategorizationResponseWithClaimIndex,
  ClaimCommonKnowledgeResultWithClaimIndex,
  ClaimSubstantiationResultWithClaimIndex,
  EvidenceWeighterResponseWithClaimIndexOutput,
  FileDocument,
  InferenceValidationResponseWithClaimIndex,
  ToulminClaim,
} from '@/lib/generated-api';
import { ClaimCitationSuggestions } from './claim-citation-suggestions';
import { ClaimLiveReports } from './claim-live-reports';
import { ClaimNeedsSubstantiationAccordion } from './claim-needs-substantiation-accordion';
import { SubstantiationResults } from './substantiation-results';
import { ClaimArgumentAnalysis } from './claim-argument-analysis';
import { ClaimCategoryResults } from './claim-category-results';
import { ClaimInferenceValidation } from './claim-inference-validation';

export interface ClaimAnalysisCardProps {
  claim: ToulminClaim;
  claimCategory?: ClaimCategorizationResponseWithClaimIndex;
  commonKnowledgeResult?: ClaimCommonKnowledgeResultWithClaimIndex;
  substantiation?: ClaimSubstantiationResultWithClaimIndex;
  references: BibliographyItem[];
  claimIndex: number;
  totalClaims: number;
  supportingFiles: FileDocument[];
  citationSuggestion?: CitationSuggestionResultWithClaimIndexOutput;
  liveReportsAnalysis?: EvidenceWeighterResponseWithClaimIndexOutput;
  inferenceValidation?: InferenceValidationResponseWithClaimIndex;
  workflowRunId?: string;
  chunkIndex?: number;
}

export function ClaimAnalysisCard({
  claim,
  claimCategory,
  commonKnowledgeResult,
  substantiation,
  references,
  supportingFiles,
  claimIndex,
  totalClaims,
  citationSuggestion,
  liveReportsAnalysis,
  inferenceValidation,
  workflowRunId,
  chunkIndex,
}: ClaimAnalysisCardProps) {
  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="font-medium">
            Claim Analysis - {claimIndex + 1} of {totalClaims}
          </p>
          <AiGeneratedLabel />
        </div>

        <p className="italic text-center">&quot;{claim.text}&quot;</p>

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
      </CardContent>
    </Card>
  );
}
