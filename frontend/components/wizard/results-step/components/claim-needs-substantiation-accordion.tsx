'use client';

import { LabeledValue } from '@/components/labeled-value';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { ClaimCommonKnowledgeResultWithClaimIndex } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronRight, ListCheck } from 'lucide-react';
import { useState } from 'react';

export interface ClaimNeedsSubstantiationAccordionProps {
  result: ClaimCommonKnowledgeResultWithClaimIndex;
  className?: string;
}

export function ClaimNeedsSubstantiationAccordion({ result, className }: ClaimNeedsSubstantiationAccordionProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const needs_substantiation = result.needs_substantiation;

  return (
    <div className={cn('border-b pb-2 space-y-4', className)}>
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 font-semibold">
            <ListCheck className="h-4 w-4" />
            Needs Substantiation Check
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
        <div className="flex items-center gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge
                variant="secondary"
                className={cn(needs_substantiation ? 'bg-orange-100 text-orange-800' : 'bg-green-100 text-green-800 ')}
              >
                {needs_substantiation ? 'Needs Substantiation' : 'No Substantiation Needed'}
              </Badge>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-sm">
              <p className="text-xs">{result.rationale}</p>
            </TooltipContent>
          </Tooltip>
        </div>
      </div>

      {isExpanded && (
        <div className="space-y-2">
          <LabeledValue label="Needs Substantiation">{result.needs_substantiation ? 'Yes' : 'No'}</LabeledValue>
          <LabeledValue label="Rationale">{result.rationale}</LabeledValue>
        </div>
      )}
    </div>
  );
}
