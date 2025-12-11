'use client';

import { LabeledValue } from '@/components/labeled-value';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { InferenceValidationResponseWithClaimIndex } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronRight, Scale } from 'lucide-react';
import { useState } from 'react';

interface ClaimInferenceValidationProps {
  inferenceValidation: InferenceValidationResponseWithClaimIndex;
}

export function ClaimInferenceValidation({ inferenceValidation }: ClaimInferenceValidationProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="border-b pb-2 space-y-4">
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 font-semibold">
            <Scale className="h-4 w-4" />
            Inference Validation
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

        <Badge
          variant="secondary"
          className={cn(inferenceValidation.valid ? 'bg-green-100 text-green-800' : 'bg-orange-100 text-orange-800')}
        >
          {inferenceValidation.valid ? 'Valid' : 'Invalid'}
        </Badge>
      </div>

      {isExpanded && (
        <div className="space-y-2">
          <LabeledValue label="Valid">{inferenceValidation.valid ? 'Yes' : 'No'}</LabeledValue>
          <LabeledValue label="Rationale">{inferenceValidation.rationale}</LabeledValue>
          <LabeledValue label="Suggested Action">{inferenceValidation.suggested_action}</LabeledValue>
        </div>
      )}
    </div>
  );
}
