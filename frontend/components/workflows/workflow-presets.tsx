'use client';

import { Check } from 'lucide-react';
import { WorkflowPreset, WorkflowRunType } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/tooltip';

/**
 * Whether the selection is exactly this preset, judged on the assessments the
 * picker is offering: anything the caller seeded that has no row here is
 * neither for nor against the match, and an assessment the preset names but
 * the picker does not offer (hidden alpha, disabled) cannot count against it.
 */
export function presetIsActive(
  preset: WorkflowRunType[],
  selectedTypes: WorkflowRunType[],
  offeredTypes: WorkflowRunType[],
): boolean {
  const offered = new Set(offeredTypes);
  const want = new Set(preset.filter((type) => offered.has(type)));
  const have = new Set(selectedTypes.filter((type) => offered.has(type)));
  return want.size > 0 && want.size === have.size && [...want].every((type) => have.has(type));
}

/**
 * The selection after choosing a preset: its assessments, among those on
 * offer, replace whatever was ticked, while a seeded type the picker does not
 * list is left as it was, the same as the bulk actions do.
 */
export function applyPreset(
  preset: WorkflowRunType[],
  selectedTypes: WorkflowRunType[],
  offeredTypes: WorkflowRunType[],
): WorkflowRunType[] {
  const offered = new Set(offeredTypes);
  const kept = selectedTypes.filter((type) => !offered.has(type));
  return [...kept, ...preset.filter((type) => offered.has(type))];
}

interface WorkflowPresetChipsProps {
  presets: WorkflowPreset[];
  selectedTypes: WorkflowRunType[];
  /** The assessments the picker lists and lets the user change. */
  offeredTypes: WorkflowRunType[];
  onSelectionChange: (types: WorkflowRunType[]) => void;
  disabled?: boolean;
  getWorkflowTypeName: (type: WorkflowRunType) => string;
}

/**
 * One chip per preset. Pressing one makes the selection that set; the chip
 * reads as pressed while the selection is exactly that set, and lets go as
 * soon as a row is changed by hand, so it also tells a reader which named set,
 * if any, the current selection is.
 */
export function WorkflowPresetChips({
  presets,
  selectedTypes,
  offeredTypes,
  onSelectionChange,
  disabled = false,
  getWorkflowTypeName,
}: WorkflowPresetChipsProps) {
  return (
    <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Presets">
      <span className="mr-0.5 font-mono text-[10px] tracking-wide text-muted-foreground uppercase">Presets</span>
      {presets.map((preset) => {
        const active = presetIsActive(preset.workflows, selectedTypes, offeredTypes);
        const offeredCount = preset.workflows.filter((type) => offeredTypes.includes(type)).length;
        return (
          <Tooltip key={preset.slug}>
            <TooltipTrigger asChild>
              <button
                type="button"
                aria-pressed={active}
                disabled={disabled}
                onClick={() => onSelectionChange(applyPreset(preset.workflows, selectedTypes, offeredTypes))}
                className={cn(
                  'inline-flex h-7 cursor-pointer items-center gap-1.5 rounded-full border px-2.5 text-xs transition-colors',
                  'focus-visible:ring-ring/50 outline-none focus-visible:ring-[3px]',
                  active
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-border bg-background text-foreground hover:bg-accent/40',
                  disabled && 'cursor-not-allowed opacity-50',
                )}
              >
                {active && <Check aria-hidden className="size-3" />}
                {preset.label}
                <span
                  className={cn(
                    'font-mono text-[10px] tabular-nums',
                    active ? 'text-primary-foreground/80' : 'text-muted-foreground',
                  )}
                >
                  {offeredCount}
                </span>
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom" align="start" className="max-w-sm space-y-1">
              <p>{preset.description}</p>
              <p className="text-[11px] opacity-80">
                Selects {preset.workflows.map((type) => getWorkflowTypeName(type)).join(', ')}.
              </p>
            </TooltipContent>
          </Tooltip>
        );
      })}
    </div>
  );
}
