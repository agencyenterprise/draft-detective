'use client';

import { LabeledValue } from '@/components/labeled-value';
import { Button } from '@/components/ui/button';
import { Claim } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronRight, Scale } from 'lucide-react';
import { useState } from 'react';

export interface ClaimArgumentAnalysisProps {
  claim: Claim;
  className?: string;
}

export function ClaimArgumentAnalysis({ claim, className }: ClaimArgumentAnalysisProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className={cn('border-b pb-2 space-y-4', className)}>
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-semibold">
          <Scale className="h-4 w-4" />
          Argument Structure
        </h3>

        <Button
          variant="ghost"
          size="xs"
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-gray-600 hover:text-gray-900"
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

      {isExpanded && (
        <div className="space-y-2">
          <LabeledValue label="Extracted Claim">{claim.claim}</LabeledValue>
          <LabeledValue label="Related text">{claim.text}</LabeledValue>
          <LabeledValue label="Rationale">{claim.rationale}</LabeledValue>
        </div>
      )}
    </div>
  );
}
