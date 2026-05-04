import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { LabeledValue } from '@/components/labeled-value';
import { Markdown } from '@/components/markdown';
import { AgentMessagesDialog } from '@/components/shared/agent-messages-dialog';
import {
  ReferenceValidationFinalResultV2,
  ReferenceValidationV2Item,
  ReferenceValidationV2Status,
} from '@/lib/generated-api';
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ChevronDownIcon,
  ChevronRightIcon,
  ClipboardCheck,
  Loader2,
  MessageSquare,
  SearchX,
  XCircle,
} from 'lucide-react';
import * as React from 'react';

function humanizeLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export interface ValidationResultsBoxV2Props {
  validation: ReferenceValidationV2Item;
  /** Whether to show the reference text in the header. */
  showReference?: boolean;
  /** Label for the reference text when showReference is true. */
  referenceLabel?: string;
  /** Size variant controlling padding. */
  size?: 'sm' | 'default';
}

const sizeClasses = {
  sm: 'py-1 px-2',
  default: 'py-3 px-4',
} as const;

export function ValidationResultsBoxV2({
  validation,
  showReference = false,
  referenceLabel = 'Reference',
  size = 'sm',
}: ValidationResultsBoxV2Props) {
  const paddingClass = sizeClasses[size];
  const [isExpanded, setIsExpanded] = React.useState(false);
  const [isMessagesOpen, setIsMessagesOpen] = React.useState(false);

  const status = validation.status ?? ReferenceValidationV2Status.Pending;
  const result = validation.validation_result;
  const hasMessages = validation.messages && validation.messages.length > 0;

  if (status === ReferenceValidationV2Status.Cancelled) {
    return (
      <div className={`rounded border ${paddingClass} bg-muted/50 border-border`}>
        <div className="flex items-center gap-2">
          <ClipboardCheck className="w-4 h-4 text-muted-foreground" />
          <span className="text-xs font-medium text-foreground">Validation results</span>
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-full border bg-muted text-muted-foreground border-border">
            <Ban className="w-3.5 h-3.5" />
            Not validated
          </span>
        </div>
      </div>
    );
  }

  if (status === ReferenceValidationV2Status.Pending) {
    return (
      <div
        className={`rounded border ${paddingClass} bg-blue-50/80 border-blue-200 dark:bg-blue-950/40 dark:border-blue-900`}
      >
        <div className="flex items-center gap-2">
          <ClipboardCheck className="w-4 h-4 text-muted-foreground" />
          <span className="text-xs font-medium text-foreground">Validation results</span>
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-full border bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Validating...
          </span>
        </div>
        {showReference && validation.input_reference && (
          <div className="pt-2 mt-2 border-t border-current/10">
            <span className="text-xs font-medium text-muted-foreground">{referenceLabel}:</span>
            <div className="text-sm mt-1 break-words">
              <Markdown>{validation.input_reference}</Markdown>
            </div>
          </div>
        )}
      </div>
    );
  }

  if (status === ReferenceValidationV2Status.Error) {
    return (
      <div
        className={`rounded border ${paddingClass} bg-red-50/80 border-red-200 dark:bg-red-950/40 dark:border-red-900`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="w-4 h-4 text-muted-foreground" />
            <span className="text-xs font-medium text-foreground">Validation results</span>
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-full border bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-800">
              <XCircle className="w-3.5 h-3.5" />
              Error
            </span>
          </div>
          <Button variant="outline" size="xs" onClick={() => setIsExpanded(!isExpanded)}>
            {isExpanded ? <ChevronDownIcon className="size-4" /> : <ChevronRightIcon className="size-4" />}
            {isExpanded ? 'Hide details' : 'Show details'}
          </Button>
        </div>
        {showReference && validation.input_reference && (
          <div className="pt-2 mt-2 border-t border-current/10">
            <span className="text-xs font-medium text-muted-foreground">{referenceLabel}:</span>
            <div className="text-sm mt-1 break-words">
              <Markdown>{validation.input_reference}</Markdown>
            </div>
          </div>
        )}
        {isExpanded && validation.error && (
          <div className="pt-2 mt-2 border-t border-current/10 text-sm text-red-700">{validation.error}</div>
        )}
      </div>
    );
  }

  if (!result) {
    return null;
  }

  const issues = result.bibliography_field_validations?.filter((field) => field.problem_type !== 'correct') || [];
  const missingCount = issues.filter((field) => field.problem_type === 'missing').length;
  const incorrectCount = issues.filter(
    (field) => field.problem_type === 'incorrect' || field.problem_type === 'other',
  ).length;
  const finalResult = result.final_result;

  const resultConfig = {
    [ReferenceValidationFinalResultV2.Correct]: {
      boxClass: 'bg-green-50/80 border-green-200 dark:bg-green-950/40 dark:border-green-900',
      badgeClass:
        'bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-800',
      icon: <CheckCircle2 className="w-3.5 h-3.5" />,
      label: 'Valid',
    },
    [ReferenceValidationFinalResultV2.MissingFields]: {
      boxClass: 'bg-yellow-50/80 border-yellow-200 dark:bg-yellow-950/40 dark:border-yellow-900',
      badgeClass:
        'bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-950 dark:text-yellow-300 dark:border-yellow-800',
      icon: <AlertTriangle className="w-3.5 h-3.5" />,
      label: `${missingCount || issues.length} missing field${(missingCount || issues.length) !== 1 ? 's' : ''}`,
    },
    [ReferenceValidationFinalResultV2.IncorrectFields]: {
      boxClass: 'bg-red-50/80 border-red-200 dark:bg-red-950/40 dark:border-red-900',
      badgeClass: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-800',
      icon: <SearchX className="w-3.5 h-3.5" />,
      label:
        incorrectCount > 0
          ? `${incorrectCount} incorrect field${incorrectCount !== 1 ? 's' : ''}`
          : 'Reference not found',
    },
  };

  const config = resultConfig[finalResult];

  return (
    <div className={`rounded border ${paddingClass} ${config.boxClass}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="w-4 h-4 text-muted-foreground" />
          <span className="text-xs font-medium text-foreground">Validation results</span>
          <span
            className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-full border ${config.badgeClass}`}
          >
            {config.icon}
            {config.label}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {hasMessages && (
            <Button variant="outline" size="xs" onClick={() => setIsMessagesOpen(true)} title="View agent messages">
              <MessageSquare className="size-4" />
              Messages
            </Button>
          )}
          <Button variant="outline" size="xs" onClick={() => setIsExpanded(!isExpanded)}>
            {isExpanded ? <ChevronDownIcon className="size-4" /> : <ChevronRightIcon className="size-4" />}
            {isExpanded ? 'Hide details' : 'Show details'}
          </Button>
        </div>
      </div>

      {showReference && validation.input_reference && (
        <div className="pt-2 mt-2 border-t border-current/10">
          <span className="text-xs font-medium text-muted-foreground">{referenceLabel}:</span>
          <div className="text-sm mt-1 break-words">
            <Markdown>{validation.input_reference}</Markdown>
          </div>
        </div>
      )}

      {isExpanded && (
        <div className="space-y-3 pt-2 mt-2 border-t border-current/10 text-sm leading-relaxed">
          <LabeledValue label="Suggested Action">
            <span className="break-words">{result.suggested_action}</span>
          </LabeledValue>

          {result.updated_reference && (
            <LabeledValue label="Updated Reference">
              <p className="break-words text-xs bg-background/50 p-2 rounded border border-border">
                {result.updated_reference}
              </p>
            </LabeledValue>
          )}

          {result.url && (
            <LabeledValue label="URL">
              <a
                href={result.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline break-all"
              >
                {result.url}
              </a>
            </LabeledValue>
          )}

          {result.reasoning && (
            <LabeledValue label="Reasoning">
              <span className="break-words">{result.reasoning}</span>
            </LabeledValue>
          )}

          {result.bibliography_field_validations && result.bibliography_field_validations.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-2">Field Validations</h4>
              <div className="space-y-2">
                {result.bibliography_field_validations.map((field, idx) => {
                  const isCorrect = field.problem_type === 'correct';
                  const isIncorrect = field.problem_type === 'incorrect' || field.problem_type === 'other';
                  return (
                    <div key={idx} className="pl-3 border-l-2 border-border text-xs">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium uppercase text-muted-foreground">
                          {humanizeLabel(field.category)}
                        </span>
                        <Badge
                          variant={isCorrect ? 'success' : 'outline'}
                          className={`text-xs ${
                            isCorrect
                              ? ''
                              : isIncorrect
                                ? 'bg-red-100 text-red-800 border-red-300 dark:bg-red-950 dark:text-red-300 dark:border-red-800'
                                : 'bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-950 dark:text-yellow-300 dark:border-yellow-800'
                          }`}
                        >
                          {isCorrect ? 'Valid' : humanizeLabel(field.problem_type)}
                        </Badge>
                      </div>
                      <div className="text-muted-foreground space-y-0.5">
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

      {hasMessages && (
        <AgentMessagesDialog
          messages={validation.messages!}
          open={isMessagesOpen}
          onOpenChange={setIsMessagesOpen}
          title={showReference && referenceLabel ? `Messages — ${referenceLabel}` : undefined}
        />
      )}
    </div>
  );
}
