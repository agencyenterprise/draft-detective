'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { CheckCircle2, XCircle } from 'lucide-react';

interface ValidationStats {
  passed: number;
  failed: number;
  total: number;
}

interface ValidationSummaryCardProps {
  /** Statistics for passed/failed validation */
  stats: ValidationStats;
  /** Title to show when all items pass */
  allPassedTitle: string;
  /** Title to show when some items fail */
  defaultTitle: string;
  /** Description to show when all items pass */
  allPassedDescription: string;
  /** Description to show when some items fail */
  defaultDescription: string;
}

/**
 * Reusable summary card that shows validation pass/fail statistics.
 * Used across QA Screener workflows (AboutThisGer, AdvocacyTone, etc.)
 *
 * Displays a success state when all items pass, otherwise shows
 * the count of passed and failed items.
 */
export function ValidationSummaryCard({
  stats,
  allPassedTitle,
  defaultTitle,
  allPassedDescription,
  defaultDescription,
}: ValidationSummaryCardProps) {
  const allPassed = stats.failed === 0 && stats.passed > 0;

  return (
    <Card
      className={allPassed ? 'border-green-200 bg-green-50/30 dark:bg-green-950/30 dark:border-green-900' : undefined}
    >
      <CardHeader>
        <div className="flex items-center gap-3">
          {allPassed && (
            <div className="h-10 w-10 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center flex-shrink-0">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
            </div>
          )}
          <div>
            <CardTitle className="text-base">{allPassed ? allPassedTitle : defaultTitle}</CardTitle>
            <CardDescription>{allPassed ? allPassedDescription : defaultDescription}</CardDescription>
          </div>
        </div>
      </CardHeader>
      {!allPassed && (
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-green-50 dark:bg-green-950/40">
              <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
              <span className="text-sm font-medium text-green-700 dark:text-green-300">{stats.passed} Passed</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-red-50 dark:bg-red-950/40">
              <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
              <span className="text-sm font-medium text-red-700 dark:text-red-300">{stats.failed} Failed</span>
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  );
}
