'use client';

import { Badge } from '@/components/ui/badge';
import { EmptyState } from '@/components/shared/empty-state';
import { ValidationResultsBox } from '@/components/results/tabs/reference-review/validation-results-box';
import {
  ReferenceValidationFinalResult,
  ReferenceValidationItem,
  ReferenceValidationState,
  ReferenceValidationStatus,
  WorkflowRunDetail,
} from '@/lib/generated-api';
import { AlertTriangle, Ban, CheckCircle2, ClipboardCheck, Loader2, SearchX, XCircle } from 'lucide-react';
import * as React from 'react';

type FilterType = 'all' | 'valid' | 'inconsistencies' | 'not_found' | 'pending' | 'error' | 'cancelled';

interface ReferenceValidationResultsProps {
  workflowDetail: WorkflowRunDetail;
}

/** Determines the category of a validation item for filtering */
function getValidationCategory(v: ReferenceValidationItem): Exclude<FilterType, 'all'> {
  const status = v.status ?? ReferenceValidationStatus.Pending;
  if (status === ReferenceValidationStatus.Pending) return 'pending';
  if (status === ReferenceValidationStatus.Error) return 'error';
  if (status === ReferenceValidationStatus.Cancelled) return 'cancelled';

  const finalResult = v.validation_result?.final_result;
  if (finalResult === ReferenceValidationFinalResult.Valid) return 'valid';
  if (finalResult === ReferenceValidationFinalResult.NotFound) return 'not_found';
  return 'inconsistencies';
}

export function ReferenceValidationResults({ workflowDetail }: ReferenceValidationResultsProps) {
  const results = workflowDetail.state as ReferenceValidationState | undefined;
  const [filter, setFilter] = React.useState<FilterType>('all');

  // Extract validations and calculate summary stats in a single pass
  const { validations, stats } = React.useMemo(() => {
    const items = results?.reference_validations ?? [];
    let pending = 0;
    let errors = 0;
    let inconsistencies = 0;
    let notFound = 0;
    let valid = 0;
    let cancelled = 0;

    items.forEach((v: ReferenceValidationItem) => {
      const category = getValidationCategory(v);
      if (category === 'pending') pending++;
      else if (category === 'error') errors++;
      else if (category === 'valid') valid++;
      else if (category === 'not_found') notFound++;
      else if (category === 'cancelled') cancelled++;
      else inconsistencies++;
    });

    return {
      validations: items,
      stats: { pending, errors, inconsistencies, notFound, valid, cancelled, total: items.length },
    };
  }, [results?.reference_validations]);

  // Filter validations based on selected filter
  const filteredValidations = React.useMemo(() => {
    if (filter === 'all') return validations;
    return validations.filter((v) => getValidationCategory(v) === filter);
  }, [validations, filter]);

  // Helper to toggle filter - clicking active filter resets to 'all'
  const toggleFilter = (newFilter: FilterType) => {
    setFilter((current) => (current === newFilter ? 'all' : newFilter));
  };

  if (validations.length === 0) {
    return <EmptyState message="No reference validation results available." />;
  }

  return (
    <div className="space-y-6">
      {/* Header with summary stats */}
      <div className="flex items-center flex-wrap gap-2">
        <ClipboardCheck className="h-5 w-5 text-blue-600" />
        <span className="text-sm font-medium">Reference Validation Results</span>
        <Badge
          variant="secondary"
          className={`ml-auto cursor-pointer transition-all ${filter === 'all' ? 'ring-2 ring-offset-1 ring-gray-400' : 'hover:bg-secondary/80'}`}
          onClick={() => toggleFilter('all')}
        >
          {stats.total} Reference{stats.total !== 1 ? 's' : ''}
        </Badge>
        {stats.valid > 0 && (
          <Badge
            variant="outline"
            className={`cursor-pointer transition-all bg-green-50 text-green-700 border-green-200 ${filter === 'valid' ? 'ring-2 ring-offset-1 ring-green-400' : 'hover:bg-green-100'}`}
            onClick={() => toggleFilter('valid')}
          >
            <CheckCircle2 className="w-3 h-3 mr-1" />
            {stats.valid} Valid
          </Badge>
        )}
        {stats.inconsistencies > 0 && (
          <Badge
            variant="outline"
            className={`cursor-pointer transition-all bg-yellow-50 text-yellow-700 border-yellow-200 ${filter === 'inconsistencies' ? 'ring-2 ring-offset-1 ring-yellow-400' : 'hover:bg-yellow-100'}`}
            onClick={() => toggleFilter('inconsistencies')}
          >
            <AlertTriangle className="w-3 h-3 mr-1" />
            {stats.inconsistencies} With Inconsistencies
          </Badge>
        )}
        {stats.notFound > 0 && (
          <Badge
            variant="outline"
            className={`cursor-pointer transition-all bg-red-50 text-red-700 border-red-200 ${filter === 'not_found' ? 'ring-2 ring-offset-1 ring-red-400' : 'hover:bg-red-100'}`}
            onClick={() => toggleFilter('not_found')}
          >
            <SearchX className="w-3 h-3 mr-1" />
            {stats.notFound} Not Found
          </Badge>
        )}
        {stats.pending > 0 && (
          <Badge
            variant="outline"
            className={`cursor-pointer transition-all bg-blue-50 text-blue-700 border-blue-200 ${filter === 'pending' ? 'ring-2 ring-offset-1 ring-blue-400' : 'hover:bg-blue-100'}`}
            onClick={() => toggleFilter('pending')}
          >
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
            {stats.pending} Pending
          </Badge>
        )}
        {stats.errors > 0 && (
          <Badge
            variant="outline"
            className={`cursor-pointer transition-all bg-red-50 text-red-700 border-red-200 ${filter === 'error' ? 'ring-2 ring-offset-1 ring-red-400' : 'hover:bg-red-100'}`}
            onClick={() => toggleFilter('error')}
          >
            <XCircle className="w-3 h-3 mr-1" />
            {stats.errors} Error{stats.errors !== 1 ? 's' : ''}
          </Badge>
        )}
        {stats.cancelled > 0 && (
          <Badge
            variant="outline"
            className={`cursor-pointer transition-all bg-gray-50 text-gray-500 border-gray-200 ${filter === 'cancelled' ? 'ring-2 ring-offset-1 ring-gray-400' : 'hover:bg-gray-100'}`}
            onClick={() => toggleFilter('cancelled')}
          >
            <Ban className="w-3 h-3 mr-1" />
            {stats.cancelled} Not Validated
          </Badge>
        )}
      </div>

      {/* List of validation results */}
      <div className="space-y-3">
        {filteredValidations.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">No references match the selected filter.</p>
        ) : (
          filteredValidations.map((validation, index) => (
            <ValidationResultsBox
              key={validation.reference_id || index}
              validation={validation}
              showReference
              referenceLabel={`Reference #${validations.indexOf(validation) + 1}`}
              size="default"
            />
          ))
        )}
      </div>
    </div>
  );
}
