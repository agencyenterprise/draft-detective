import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { LabeledValue } from '@/components/labeled-value';
import { BibliographyItemValidation } from '@/lib/generated-api';
import { AlertTriangle, CheckCircle2, ChevronDownIcon, ChevronRightIcon, ClipboardCheck } from 'lucide-react';
import * as React from 'react';

function humanizeLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export interface ValidationResultsBoxProps {
  validation: BibliographyItemValidation;
}

export function ValidationResultsBox({ validation }: ValidationResultsBoxProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);

  const issues = validation.bibliography_field_validations?.filter((field) => field.problem_type !== 'correct') || [];
  const hasIssues = issues.length > 0;
  const isValid = validation.valid_reference && !hasIssues;

  const getBoxColorClass = () => {
    if (isValid) return 'bg-green-50/80 border-green-200';
    return 'bg-yellow-50/80 border-yellow-200';
  };

  return (
    <div className={`rounded border py-1 px-2 ${getBoxColorClass()}`}>
      {/* Header with title and badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="w-4 h-4 text-muted-foreground" />
          <span className="text-xs font-medium text-gray-700">Validation results</span>
          {isValid ? (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-full border bg-green-50 text-green-700 border-green-200">
              <CheckCircle2 className="w-3.5 h-3.5" />
              No issues
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-full border bg-yellow-50 text-yellow-700 border-yellow-200">
              <AlertTriangle className="w-3.5 h-3.5" />
              {issues.length} issue{issues.length !== 1 ? 's' : ''} found
            </span>
          )}
        </div>
        <Button variant="outline" size="xs" onClick={() => setIsExpanded(!isExpanded)}>
          {isExpanded ? <ChevronDownIcon className="size-4" /> : <ChevronRightIcon className="size-4" />}
          {isExpanded ? 'Hide details' : 'Show details'}
        </Button>
      </div>

      {/* Expanded details */}
      {isExpanded && (
        <div className="space-y-3 pt-2 mt-2 border-t border-current/10 text-sm leading-relaxed">
          {/* Suggested action */}
          <LabeledValue label="Suggested Action">
            <span className="break-words">{validation.suggested_action}</span>
          </LabeledValue>

          {/* Updated reference if available */}
          {validation.updated_reference && (
            <LabeledValue label="Updated Reference">
              <p className="break-words text-xs bg-white/50 p-2 rounded border border-gray-200">
                {validation.updated_reference}
              </p>
            </LabeledValue>
          )}

          {/* URL */}
          {validation.url && (
            <LabeledValue label="URL">
              <a
                href={validation.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline break-all"
              >
                {validation.url}
              </a>
            </LabeledValue>
          )}

          {/* Reasoning */}
          {validation.reasoning && (
            <LabeledValue label="Reasoning">
              <span className="break-words">{validation.reasoning}</span>
            </LabeledValue>
          )}

          {/* Field validations */}
          {validation.bibliography_field_validations && validation.bibliography_field_validations.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-2">Field Validations</h4>
              <div className="space-y-2">
                {validation.bibliography_field_validations.map((field, idx) => {
                  const isCorrect = field.problem_type === 'correct';
                  return (
                    <div key={idx} className="pl-3 border-l-2 border-gray-200 text-xs">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium uppercase text-gray-600">{humanizeLabel(field.category)}</span>
                        <Badge
                          variant={isCorrect ? 'success' : 'outline'}
                          className={`text-xs ${
                            isCorrect
                              ? ''
                              : 'bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-900/20 dark:text-yellow-400 dark:border-yellow-800'
                          }`}
                        >
                          {isCorrect ? 'Valid' : humanizeLabel(field.problem_type)}
                        </Badge>
                      </div>
                      <div className="text-gray-600 space-y-0.5">
                        {field.current_value && (
                          <div className="break-words">
                            <span className="font-medium">Current:</span> {field.current_value}
                          </div>
                        )}
                        {field.suggested_value && field.problem_type !== 'correct' && (
                          <div className="break-words">
                            <span className="font-medium">Suggested:</span> {field.suggested_value}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
