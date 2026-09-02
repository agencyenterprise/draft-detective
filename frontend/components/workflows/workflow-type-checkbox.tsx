'use client';

import * as React from 'react';
import * as CheckboxPrimitive from '@radix-ui/react-checkbox';
import {
  CheckIcon,
  FlaskConical,
  Search,
  FileText,
  Link,
  FileSearch,
  Scale,
  Download,
  Library,
  Newspaper,
  FileCheck,
  BarChart3,
  BrainCircuit,
  ClipboardCheck,
  Files,
  ShieldCheck,
  MessageSquareWarning,
  ALargeSmall,
  BookOpen,
  Clock,
  type LucideIcon,
  FileCheckIcon,
  TableIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { WorkflowGate, WorkflowRunType, WorkflowTypeDescription } from '@/lib/generated-api';
import { Badge } from '../ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/tooltip';
import { formatEstimatedDuration } from './utils';

// Partial: WorkflowRunType keeps members whose workflow has been removed, so
// old runs still deserialize. Those have no icon; getWorkflowIcon falls back.
const workflowTypeIcons: Partial<Record<WorkflowRunType, LucideIcon>> = {
  [WorkflowRunType.DocumentProcessing]: FileText,
  [WorkflowRunType.DocumentSummarization]: FileText,
  [WorkflowRunType.ReferenceExtraction]: Link,
  [WorkflowRunType.ReferenceFileMatching]: FileSearch,
  [WorkflowRunType.MethodologicalAlignment]: Scale,
  [WorkflowRunType.ReferenceDownloader]: Download,
  [WorkflowRunType.LiteratureReviewV2]: Library,
  [WorkflowRunType.LiveReportsV2]: Newspaper,
  [WorkflowRunType.ReferenceValidationV2]: FileCheck,
  [WorkflowRunType.ResultsExtraction]: BarChart3,
  [WorkflowRunType.InferenceValidationV2]: BrainCircuit,
  [WorkflowRunType.ClaimReferenceValidationV2]: ClipboardCheck,
  [WorkflowRunType.AbbreviationScanV2]: ALargeSmall,
  [WorkflowRunType.AdvocacyToneV2]: MessageSquareWarning,
  [WorkflowRunType.AboutThisGer]: BookOpen,
  [WorkflowRunType.Reviewer2]: BookOpen,
  [WorkflowRunType.DocumentStructure]: FileCheckIcon,
  [WorkflowRunType.FiguresTablesCheck]: TableIcon,
  [WorkflowRunType.RecommendationCheck]: ClipboardCheck,
  [WorkflowRunType.RevisionPlanningSummary]: ClipboardCheck,
  [WorkflowRunType.ReviewerResponseMemos]: MessageSquareWarning,
  [WorkflowRunType.ReviewerCoverageReport]: ShieldCheck,
};

const DEFAULT_ICON = FileText;

function getWorkflowIcon(type: WorkflowRunType): LucideIcon {
  return workflowTypeIcons[type] ?? DEFAULT_ICON;
}

interface WorkflowTypeCheckboxProps {
  workflowType: WorkflowTypeDescription;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  /** Median run time in seconds, from historical runs. Hidden when unavailable. */
  estimatedSeconds?: number | null;
}

export function WorkflowTypeCheckbox({
  workflowType,
  checked,
  onCheckedChange,
  disabled = false,
  estimatedSeconds,
}: WorkflowTypeCheckboxProps) {
  const Icon = getWorkflowIcon(workflowType.type);
  const requiresSupportingFiles = workflowType.gates.includes(WorkflowGate.ReferenceReview);
  const estimatedDuration = formatEstimatedDuration(estimatedSeconds);

  return (
    <label
      htmlFor={workflowType.type}
      className={cn(
        'group rounded-xl p-3 cursor-pointer transition-all block border h-full',
        'hover:bg-accent/50 hover:border-accent',
        checked ? 'border-primary bg-primary/5' : 'border-border',
        disabled && 'cursor-not-allowed opacity-50',
      )}
    >
      <div className="flex gap-3">
        <div
          className={cn(
            'flex items-center justify-center size-8 rounded-lg shrink-0 transition-colors',
            checked ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground',
          )}
        >
          <Icon className="size-4" />
        </div>

        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex items-start justify-between gap-3">
            <span className={cn('text-sm font-medium leading-tight', disabled && 'opacity-70')}>
              {workflowType.name}
            </span>
            <CheckboxPrimitive.Root
              id={workflowType.type}
              checked={checked}
              onCheckedChange={onCheckedChange}
              disabled={disabled}
              data-slot="checkbox"
              className={cn(
                'peer border-input dark:bg-input/30 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground dark:data-[state=checked]:bg-primary data-[state=checked]:border-primary focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive size-5 shrink-0 rounded-md border shadow-xs transition-shadow outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50',
              )}
            >
              <CheckboxPrimitive.Indicator
                data-slot="checkbox-indicator"
                className="flex items-center justify-center text-current transition-none"
              >
                <CheckIcon className="size-4" />
              </CheckboxPrimitive.Indicator>
            </CheckboxPrimitive.Root>
          </div>

          <p className="text-sm text-muted-foreground">{workflowType.description}</p>

          {(estimatedDuration ||
            workflowType.is_experimental ||
            workflowType.needs_web_search ||
            requiresSupportingFiles) && (
            <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
              {estimatedDuration && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="outline" className="flex items-center gap-1 text-xs">
                      <Clock className="size-3" />
                      {estimatedDuration}
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="max-w-xs">
                    Rough estimate based on how long this assessment has taken on past documents. Actual time varies
                    with document size and current system load.
                  </TooltipContent>
                </Tooltip>
              )}
              {requiresSupportingFiles && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="warning" className="flex items-center gap-1 text-xs">
                      <Files className="size-3" />
                      Needs Full Text References
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="max-w-xs">
                    This assessment requires the full text of referenced documents. Claims citing references without
                    matched source documents will be skipped. You can upload sources or fetch from the web in Step 3.
                  </TooltipContent>
                </Tooltip>
              )}
              {workflowType.needs_web_search && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="outline" className="flex items-center gap-1 text-xs">
                      <Search className="size-3" />
                      Web Search
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="max-w-xs">
                    This assessment searches the web (using a web search tool) for additional context and information to
                    enhance the assessment. Parts of the document might be used as web search query/context.
                  </TooltipContent>
                </Tooltip>
              )}
              {workflowType.is_experimental && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="secondary" className="flex items-center gap-1 text-xs">
                      <FlaskConical className="size-3" />
                      Alpha
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="max-w-xs">
                    This assessment is in alpha. Results may vary and features/performance may change in future updates.
                  </TooltipContent>
                </Tooltip>
              )}
            </div>
          )}
        </div>
      </div>
    </label>
  );
}
