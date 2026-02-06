'use client';

import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { CheckCircle2, ChevronDown, XCircle } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';

interface CheckStatusItemProps {
  /** Whether the check passed */
  passed: boolean;
  /** The label for this check */
  label: string;
  /** Explanation text */
  explanation?: string;
  /** Whether this check is applicable (shows N/A if false) */
  applicable?: boolean;
  /** Optional level badge (e.g., "sentence", "paragraph") */
  level?: string;
  /** Optional matched text to display */
  matchedText?: string;
  /** Whether the item can be expanded (default: true if has explanation or matchedText) */
  expandable?: boolean;
}

/**
 * Reusable status item for displaying pass/fail checks.
 * Used in QA Screener workflows for requirement and rule validation.
 *
 * Supports two modes:
 * 1. Simple: Just shows passed/failed icon with label
 * 2. Expandable: Collapsible with explanation and matched text
 */
export function CheckStatusItem({
  passed,
  label,
  explanation,
  applicable = true,
  level,
  matchedText,
  expandable,
}: CheckStatusItemProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Auto-determine if expandable based on content
  const isExpandable = expandable ?? (!!explanation || !!matchedText);

  // Not applicable state
  if (!applicable) {
    return (
      <div className="flex items-start gap-2 text-sm text-muted-foreground">
        <span className="text-muted-foreground mt-0.5">—</span>
        <div>
          <span className="font-medium">{label}</span>
          <span className="text-xs ml-2">(N/A)</span>
        </div>
      </div>
    );
  }

  // Simple non-expandable mode
  if (!isExpandable) {
    return (
      <div className={cn('flex items-start gap-2 text-sm', passed ? 'text-green-700' : 'text-red-700')}>
        {passed ? (
          <CheckCircle2 className="h-4 w-4 mt-0.5 flex-shrink-0" />
        ) : (
          <XCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
        )}
        <div>
          <span className="font-medium">{label}</span>
          {level && (
            <Badge variant="outline" className="ml-2 text-xs">
              {level}
            </Badge>
          )}
          {explanation && (
            <p className={cn('text-xs mt-0.5', passed ? 'text-green-600/70' : 'text-muted-foreground')}>
              {explanation}
            </p>
          )}
        </div>
      </div>
    );
  }

  // Expandable mode with collapsible
  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <button
          className={cn(
            'w-full flex items-start gap-2 text-sm p-2 rounded-md transition-colors hover:bg-muted/50',
            passed ? 'text-green-700' : 'text-red-700',
          )}
        >
          {passed ? (
            <CheckCircle2 className="h-4 w-4 mt-0.5 flex-shrink-0" />
          ) : (
            <XCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
          )}
          <div className="flex-1 text-left">
            <span className="font-medium">{label}</span>
            {level && (
              <Badge variant="outline" className="ml-2 text-xs">
                {level}
              </Badge>
            )}
          </div>
          <ChevronDown className={cn('h-4 w-4 transition-transform', isOpen && 'rotate-180')} />
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="ml-6 p-2 space-y-2">
          {explanation && (
            <p className={cn('text-xs', passed ? 'text-green-600/70' : 'text-muted-foreground')}>{explanation}</p>
          )}
          {matchedText && (
            <div className="p-2 rounded-md bg-muted/50 border text-xs">
              <p className="font-medium text-muted-foreground mb-1">Matched {level ?? 'text'}:</p>
              <p className="text-foreground">{matchedText}</p>
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
