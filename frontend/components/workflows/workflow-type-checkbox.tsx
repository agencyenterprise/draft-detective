'use client';

import * as React from 'react';
import {
  FilePenLine,
  FlaskConical,
  Globe,
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
import { DynamicIcon, iconNames, type IconName } from 'lucide-react/dynamic';
import { cn } from '@/lib/utils';
import { RAIL_ITEM_IDLE } from '@/lib/rail-style';
import { WorkflowGate, WorkflowRunType, WorkflowTypeDescription } from '@/lib/generated-api';
import { Badge } from '../ui/badge';
import { Checkbox } from '../ui/checkbox';
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/tooltip';
import { formatEstimatedDuration } from './utils';

// Partial: WorkflowRunType keeps members whose workflow has been removed, so
// old runs still deserialize. Those have no icon; WorkflowIcon falls back.
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

/** Every icon name lucide ships, as a set so a render-time lookup is constant time. */
const LUCIDE_ICON_NAMES: ReadonlySet<string> = new Set(iconNames);

/**
 * The lucide icon a workflow declares, when lucide knows the name. Anything
 * else (no declaration, a typo, an icon from another set) resolves to null so
 * the caller falls back instead of asking DynamicIcon for a name it will reject.
 */
export function declaredIconName(icon: string | null | undefined): IconName | null {
  return icon && LUCIDE_ICON_NAMES.has(icon) ? (icon as IconName) : null;
}

/**
 * The icon for an assessment. A workflow that declares a lucide icon name
 * (skill-declared workflows do, in their SKILL.md frontmatter) is drawn from
 * that name; the hand-written workflows keep their entries in the map above.
 */
export function WorkflowIcon({
  workflowType,
  className,
}: {
  workflowType: WorkflowTypeDescription;
  className?: string;
}) {
  const declared = declaredIconName(workflowType.icon);
  if (declared) {
    return <DynamicIcon name={declared} className={className} />;
  }
  const Icon: LucideIcon = workflowTypeIcons[workflowType.type] ?? DEFAULT_ICON;
  return <Icon className={className} />;
}

/**
 * A trait of the assessment, as a small labelled badge with a tooltip that
 * explains it. The label stays: an icon on its own says little, and these
 * traits are what a reader weighs before ticking the row.
 */
function TraitBadge({
  icon: Icon,
  label,
  tooltip,
  variant = 'outline',
}: {
  icon: LucideIcon;
  label: string;
  tooltip: string;
  variant?: 'outline' | 'secondary';
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant={variant} className="h-5 gap-1 px-1.5 text-[11px] font-normal">
          <Icon aria-hidden className="size-3" />
          {label}
        </Badge>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs">
        {tooltip}
      </TooltipContent>
    </Tooltip>
  );
}

interface WorkflowTypeCheckboxProps {
  workflowType: WorkflowTypeDescription;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  /** Median run time in seconds, from historical runs. Hidden when unavailable. */
  estimatedSeconds?: number | null;
}

/**
 * One assessment in the picker: a rail-style row rather than a card, so the
 * list reads like the assessments tab beside it. Checkbox, icon, name and a
 * one-line description, with the assessment's traits as marks at the far end.
 */
export function WorkflowTypeCheckbox({
  workflowType,
  checked,
  onCheckedChange,
  disabled = false,
  estimatedSeconds,
}: WorkflowTypeCheckboxProps) {
  const requiresSupportingFiles = workflowType.gates.includes(WorkflowGate.ReferenceReview);
  const estimatedDuration = formatEstimatedDuration(estimatedSeconds);

  return (
    <label
      htmlFor={workflowType.type}
      className={cn(
        'group flex w-full cursor-pointer items-center gap-3 rounded-md px-2 py-2 transition-colors',
        // The primary tint the card design used, not the rail's foreground wash:
        // a dozen selected rows in grey read as a disabled list.
        checked ? 'bg-primary/5 hover:bg-primary/10' : RAIL_ITEM_IDLE,
        disabled && 'cursor-not-allowed opacity-50',
      )}
    >
      <Checkbox id={workflowType.type} checked={checked} onCheckedChange={onCheckedChange} disabled={disabled} />

      <span
        className={cn(
          'flex size-7 shrink-0 items-center justify-center rounded-md transition-colors',
          checked ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground',
        )}
      >
        <WorkflowIcon workflowType={workflowType} className="size-4" />
      </span>

      <span className="min-w-0 flex-1">
        {/* The traits share the name's line, so the row keeps to its name and
            description and the badges read as qualifiers of the name. */}
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="truncate text-sm font-medium leading-tight">{workflowType.name}</span>
          {requiresSupportingFiles && (
            <TraitBadge
              icon={Files}
              label="Needs Full Text References"
              tooltip="This assessment requires the full text of referenced documents. Claims citing references without matched source documents will be skipped. You can upload sources or fetch from the web in the References tab."
            />
          )}
          {workflowType.needs_web_search && (
            <TraitBadge
              icon={Globe}
              label="Web Search"
              tooltip="This assessment searches the web (using a web search tool) for additional context and information to enhance the assessment. Parts of the document might be used as web search query/context."
            />
          )}
          {workflowType.proposes_edits && (
            <TraitBadge
              icon={FilePenLine}
              label="Proposed Edits"
              tooltip="This assessment attaches a proposed rewrite to issues where the fix is fully determined, shown alongside the original text in the document view."
            />
          )}
          {workflowType.is_experimental && (
            <TraitBadge
              icon={FlaskConical}
              label="Alpha"
              variant="secondary"
              tooltip="This assessment is in alpha. Results may vary and features/performance may change in future updates."
            />
          )}
        </span>
        {/* Two lines at most, so a long description cannot turn a row into a
            paragraph. The whole of it is in the tooltip for the mouse, and the
            clamp lifts while the row's checkbox has keyboard focus, so a
            keyboard user reads it in place without a tab stop per row. */}
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="mt-0.5 line-clamp-2 text-[13px] leading-snug text-muted-foreground group-has-[:focus-visible]:line-clamp-none">
              {workflowType.description}
            </span>
          </TooltipTrigger>
          <TooltipContent side="bottom" align="start" className="max-w-md">
            {workflowType.description}
          </TooltipContent>
        </Tooltip>
      </span>

      {/* The estimate is a value, not a trait, so it keeps a column of its own at
          the row's end where the figures line up. */}
      {estimatedDuration && (
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="flex min-w-16 shrink-0 items-center justify-end gap-1 text-[11px] tabular-nums text-muted-foreground">
              <Clock aria-hidden className="size-3.5" />
              {estimatedDuration}
              <span className="sr-only">estimated</span>
            </span>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-xs">
            Rough estimate based on how long this assessment has taken on past documents. Actual time varies with
            document size and current system load.
          </TooltipContent>
        </Tooltip>
      )}
    </label>
  );
}
