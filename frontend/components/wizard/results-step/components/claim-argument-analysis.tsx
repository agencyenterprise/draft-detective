'use client';

import { LabeledValue } from '@/components/labeled-value';
import { Button } from '@/components/ui/button';
import { ToulminClaim } from '@/lib/generated-api/models/ToulminClaim';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronRight, Scale } from 'lucide-react';
import { useState } from 'react';

export interface ClaimArgumentAnalysisProps {
  claim: ToulminClaim;
  className?: string;
}

export function ClaimArgumentAnalysis({ claim, className }: ClaimArgumentAnalysisProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const isToulmin = claim.data || claim.warrants || claim.qualifiers || claim.rebuttals || claim.backing;

  return (
    <div className={cn('border-b pb-2 space-y-4', className)}>
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-semibold">
          <Scale className="h-4 w-4" />
          Argument Structure {isToulmin ? '(Toulmin)' : ''}
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

          {isToulmin && (
            <>
              <h4 className="font-medium text-base">Toulmin Elements</h4>
              <div className="space-y-2">
                <LabeledValue label="Data">
                  {claim.data && claim.data.length > 0 ? (
                    <ul className="list-disc pl-5">
                      {claim.data.map((data) => (
                        <li key={data}>{data}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="text-muted-foreground">None</span>
                  )}
                </LabeledValue>
                <LabeledValue label="Warrants">
                  {claim.warrants && claim.warrants.length > 0 ? (
                    <ul className="list-disc pl-5">
                      {claim.warrants.map((warrant) => (
                        <li key={warrant}>{warrant}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="text-muted-foreground">None</span>
                  )}
                </LabeledValue>
                <LabeledValue label="Qualifiers">
                  {claim.qualifiers && claim.qualifiers.length > 0 ? (
                    <ul className="list-disc pl-5">
                      {claim.qualifiers.map((qualifier) => (
                        <li key={qualifier}>{qualifier}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="text-muted-foreground">None</span>
                  )}
                </LabeledValue>
                <LabeledValue label="Rebuttals">
                  {claim.rebuttals && claim.rebuttals.length > 0 ? (
                    <ul className="list-disc pl-5">
                      {claim.rebuttals.map((rebuttal) => (
                        <li key={rebuttal}>{rebuttal}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="text-muted-foreground">None</span>
                  )}
                </LabeledValue>
                <LabeledValue label="Backing">
                  {claim.backing && claim.backing.length > 0 ? (
                    <ul className="list-disc pl-5">
                      {claim.backing.map((backing) => (
                        <li key={backing}>{backing}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="text-muted-foreground">None</span>
                  )}
                </LabeledValue>
                <LabeledValue label="Warrant Expression">
                  {claim.warrantExpression ? (
                    <span>{claim.warrantExpression}</span>
                  ) : (
                    <span className="text-muted-foreground">None</span>
                  )}
                </LabeledValue>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
