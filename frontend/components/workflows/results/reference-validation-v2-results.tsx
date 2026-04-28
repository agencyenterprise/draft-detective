'use client';

import { Badge } from '@/components/ui/badge';
import { EmptyState } from '@/components/shared/empty-state';
import { ValidationResultsBoxV2 } from '@/components/results/tabs/reference-review/validation-results-box-v2';
import {
  ReferenceValidationFinalResultV2,
  ReferenceValidationV2Item,
  ReferenceValidationV2State,
  ReferenceValidationV2Status,
  WorkflowRunDetail,
} from '@/lib/generated-api';
import { AlertTriangle, Ban, CheckCircle2, ClipboardCheck, Loader2, XCircle } from 'lucide-react';
import * as React from 'react';

type FilterType = 'all' | 'correct' | 'missing_fields' | 'incorrect_fields' | 'pending' | 'error' | 'cancelled';

interface ReferenceValidationV2ResultsProps {
  workflowDetail: WorkflowRunDetail;
}

function getValidationCategory(v: ReferenceValidationV2Item): Exclude<FilterType, 'all'> {
  const status = v.status ?? ReferenceValidationV2Status.Pending;
  if (status === ReferenceValidationV2Status.Pending) return 'pending';
  if (status === ReferenceValidationV2Status.Error) return 'error';
  if (status === ReferenceValidationV2Status.Cancelled) return 'cancelled';

  const finalResult = v.validation_result?.final_result;
  if (finalResult === ReferenceValidationFinalResultV2.Correct) return 'correct';
  if (finalResult === ReferenceValidationFinalResultV2.MissingFields) return 'missing_fields';
  return 'incorrect_fields';
}

export function ReferenceValidationV2Results({ workflowDetail }: ReferenceValidationV2ResultsProps) {
  const results = workflowDetail.state as ReferenceValidationV2State | undefined;
  const [filter, setFilter] = React.useState<FilterType>('all');

  const { validations, stats } = React.useMemo(() => {
    const items = results?.reference_validations ?? [];
    let pending = 0;
    let errors = 0;
    let missingFields = 0;
    let incorrectFields = 0;
    let correct = 0;
    let cancelled = 0;

    items.forEach((v: ReferenceValidationV2Item) => {
      const category = getValidationCategory(v);
      if (category === 'pending') pending++;
      else if (category === 'error') errors++;
      else if (category === 'correct') correct++;
      else if (category === 'missing_fields') missingFields++;
      else if (category === 'cancelled') cancelled++;
      else incorrectFields++;
    });

    return {
      validations: items,
      stats: { pending, errors, missingFields, incorrectFields, correct, cancelled, total: items.length },
    };
  }, [results?.reference_validations]);

  const filteredValidations = React.useMemo(() => {
    if (filter === 'all') return validations;
    return validations.filter((v) => getValidationCategory(v) === filter);
  }, [validations, filter]);

  const toggleFilter = (newFilter: FilterType) => {
    setFilter((current) => (current === newFilter ? 'all' : newFilter));
  };

  if (validations.length === 0) {
    return <EmptyState message="No reference validation results available." />;
  }

  return (
    <div className="space-y-6">
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
        {stats.correct > 0 && (
          <Badge
            variant="outline"
            className={`cursor-pointer transition-all bg-green-50 text-green-700 border-green-200 ${filter === 'correct' ? 'ring-2 ring-offset-1 ring-green-400' : 'hover:bg-green-100'}`}
            onClick={() => toggleFilter('correct')}
          >
            <CheckCircle2 className="w-3 h-3 mr-1" />
            {stats.correct} Correct
          </Badge>
        )}
        {stats.missingFields > 0 && (
          <Badge
            variant="outline"
            className={`cursor-pointer transition-all bg-yellow-50 text-yellow-700 border-yellow-200 ${filter === 'missing_fields' ? 'ring-2 ring-offset-1 ring-yellow-400' : 'hover:bg-yellow-100'}`}
            onClick={() => toggleFilter('missing_fields')}
          >
            <AlertTriangle className="w-3 h-3 mr-1" />
            {stats.missingFields} Missing Fields
          </Badge>
        )}
        {stats.incorrectFields > 0 && (
          <Badge
            variant="outline"
            className={`cursor-pointer transition-all bg-red-50 text-red-700 border-red-200 ${filter === 'incorrect_fields' ? 'ring-2 ring-offset-1 ring-red-400' : 'hover:bg-red-100'}`}
            onClick={() => toggleFilter('incorrect_fields')}
          >
            <XCircle className="w-3 h-3 mr-1" />
            {stats.incorrectFields} Incorrect Fields
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

      <div className="space-y-3">
        {filteredValidations.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">No references match the selected filter.</p>
        ) : (
          filteredValidations.map((validation, index) => (
            <ValidationResultsBoxV2
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
