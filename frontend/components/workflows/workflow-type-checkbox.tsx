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
  UserCheck,
  StickyNote,
  Quote,
  BookMarked,
  Scale,
  Download,
  Library,
  Newspaper,
  FileCheck,
  Lightbulb,
  BarChart3,
  BrainCircuit,
  ClipboardCheck,
  Files,
  ShieldCheck,
  MessageSquareWarning,
  ALargeSmall,
  Users,
  BookOpen,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { WorkflowRunType, WorkflowTypeDescription } from '@/lib/generated-api';
import { Badge } from '../ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/tooltip';
import { isQaScreenerWorkflow, WORKFLOWS_REQUIRING_SUPPORTING_DOCUMENTS } from './utils';

const workflowTypeIcons: Record<WorkflowRunType, LucideIcon> = {
  [WorkflowRunType.DocumentProcessing]: FileText,
  [WorkflowRunType.ChunkSplitting]: FileText,
  [WorkflowRunType.DocumentSummarization]: FileText,
  [WorkflowRunType.ReferenceExtraction]: Link,
  [WorkflowRunType.ReferenceFileMatching]: FileSearch,
  [WorkflowRunType.HumanApproval]: UserCheck,
  [WorkflowRunType.FootnoteExtraction]: StickyNote,
  [WorkflowRunType.ClaimExtraction]: Quote,
  [WorkflowRunType.CitationDetection]: BookMarked,
  [WorkflowRunType.MethodologicalAlignment]: Scale,
  [WorkflowRunType.ReferenceDownloader]: Download,
  [WorkflowRunType.LiteratureReview]: Library,
  [WorkflowRunType.LiveReports]: Newspaper,
  [WorkflowRunType.ReferenceValidation]: FileCheck,
  [WorkflowRunType.CitationSuggester]: Lightbulb,
  [WorkflowRunType.ResultsExtraction]: BarChart3,
  [WorkflowRunType.InferenceValidation]: BrainCircuit,
  [WorkflowRunType.ClaimReferenceValidation]: ClipboardCheck,
  [WorkflowRunType.AbbreviationScan]: ALargeSmall,
  [WorkflowRunType.AdvocacyTone]: MessageSquareWarning,
  [WorkflowRunType.AboutAuthors]: Users,
  [WorkflowRunType.AboutThis]: BookOpen,
};

const DEFAULT_ICON = FileText;

function getWorkflowIcon(type: WorkflowRunType): LucideIcon {
  return workflowTypeIcons[type] ?? DEFAULT_ICON;
}

function needsSupportingFiles(type: WorkflowRunType): boolean {
  return WORKFLOWS_REQUIRING_SUPPORTING_DOCUMENTS.includes(type);
}

function isFromQaScreener(type: WorkflowRunType): boolean {
  return isQaScreenerWorkflow(type);
}

interface WorkflowTypeCheckboxProps {
  workflowType: WorkflowTypeDescription;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
}

export function WorkflowTypeCheckbox({
  workflowType,
  checked,
  onCheckedChange,
  disabled = false,
}: WorkflowTypeCheckboxProps) {
  const Icon = getWorkflowIcon(workflowType.type);
  const requiresSupportingFiles = needsSupportingFiles(workflowType.type);
  const isQaScreener = isFromQaScreener(workflowType.type);

  return (
    <label
      htmlFor={workflowType.type}
      className={cn(
        'group rounded-xl p-4 cursor-pointer transition-all block border',
        'hover:bg-accent/50 hover:border-accent',
        checked ? 'border-primary bg-primary/5' : 'border-border',
        disabled && 'cursor-not-allowed opacity-50',
      )}
    >
      <div className="flex gap-4">
        <div
          className={cn(
            'flex items-center justify-center size-10 rounded-lg shrink-0 transition-colors',
            checked ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground',
          )}
        >
          <Icon className="size-5" />
        </div>

        <div className="flex-1 min-w-0 space-y-1.5">
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

          <p className="text-sm text-muted-foreground leading-relaxed">{workflowType.description}</p>

          {(workflowType.is_experimental ||
            workflowType.needs_web_search ||
            requiresSupportingFiles ||
            isQaScreener) && (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              {isQaScreener && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="default" className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-700">
                      <ShieldCheck className="size-3" />
                      QA Screener
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="max-w-xs">
                    This analysis is part of the QA Screener tool, designed for quality assurance screening of
                    documents.
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
                    This analysis requires finding / uploading the full text of reference documents. You can upload them
                    or fetch from the web in Step 3.
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
                    This analysis searches the web (using OpenAI&apos;s web search tool) for additional context and
                    information to enhance the analysis. Parts of the document might be used as web search
                    query/context.
                  </TooltipContent>
                </Tooltip>
              )}
              {workflowType.is_experimental && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="secondary" className="flex items-center gap-1 text-xs">
                      <FlaskConical className="size-3" />
                      Experimental
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="max-w-xs">
                    This analysis is still highly experimental and being refined. Results may vary and the feature may
                    change in future updates.
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
