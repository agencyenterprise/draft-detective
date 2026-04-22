'use client';

import { LabeledValue } from '@/components/labeled-value';
import { Button } from '@/components/ui/button';
import { EvidenceWeighterResponseWithClaimIndex } from '@/lib/generated-api';
import { ChevronDown, ChevronRight, EarthIcon } from 'lucide-react';
import { useState } from 'react';
import { EvidenceWeighterRecommendedActionBadge } from './evidence-weighter-recommended-action-badge';
import Link from 'next/link';

interface ClaimLiveReportsProps {
  liveReportsAnalysis: EvidenceWeighterResponseWithClaimIndex;
}

export function ClaimLiveReports({ liveReportsAnalysis }: ClaimLiveReportsProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="border-b pb-2 space-y-4">
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 font-semibold">
            <EarthIcon className="h-4 w-4" />
            Live Reports Analysis
          </h3>

          <Button
            variant="ghost"
            size="xs"
            className="text-gray-600 hover:text-gray-900"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? (
              <>
                <ChevronDown />
                Hide Details
              </>
            ) : (
              <>
                <ChevronRight />
                Show Details
              </>
            )}
          </Button>
        </div>

        <EvidenceWeighterRecommendedActionBadge recommendedAction={liveReportsAnalysis.claim_update_action} />
      </div>

      {isExpanded && (
        <div className="space-y-2">
          <LabeledValue label="Claim Update Action">{liveReportsAnalysis.claim_update_action}</LabeledValue>
          <LabeledValue label="Confidence Level">{liveReportsAnalysis.confidence_level}</LabeledValue>
          <LabeledValue label="Newer References Alignment">
            {liveReportsAnalysis.newer_references_alignment}
          </LabeledValue>
          <LabeledValue label="Rationale">{liveReportsAnalysis.rationale}</LabeledValue>
          <LabeledValue label="Rewritten Claim">
            <p className="italic">&quot;{liveReportsAnalysis.rewritten_claim}&quot;</p>
          </LabeledValue>

          <h3 className="font-medium">Newer References:</h3>
          <div className="space-y-2">
            {liveReportsAnalysis.newer_references.map((reference) => (
              <div key={reference.title} className="bg-muted p-3 rounded-md">
                <LabeledValue label="Title">{reference.title}</LabeledValue>
                <LabeledValue label="Authors">{reference.authors}</LabeledValue>
                <LabeledValue label="Publication Year">{reference.publication_year}</LabeledValue>
                <LabeledValue label="Link">
                  <Link
                    href={reference.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 underline break-all"
                  >
                    {reference.link}
                  </Link>
                </LabeledValue>
                <LabeledValue label="Bibliography Info">{reference.bibliography_info}</LabeledValue>
                <LabeledValue label="Reference Excerpt">{reference.reference_excerpt}</LabeledValue>
                <LabeledValue label="Reference Type">{reference.reference_type}</LabeledValue>
                <LabeledValue label="Reference Direction">{reference.reference_direction}</LabeledValue>
                <LabeledValue label="Quality">{reference.quality}</LabeledValue>
                <LabeledValue label="Political Bias">{reference.political_bias}</LabeledValue>
                <LabeledValue label="Rationale">{reference.rationale}</LabeledValue>
                <LabeledValue label="Methodology">{reference.methodology}</LabeledValue>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
