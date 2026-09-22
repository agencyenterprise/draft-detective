'use client';

import { Button } from '@/components/ui/button';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { WorkflowRunType } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { RAIL_ITEM_ACTIVE, RAIL_ITEM_IDLE } from '@/lib/rail-style';
import { cn } from '@/lib/utils';
import { Check, ChevronRight, ListFilter } from 'lucide-react';
import { useState } from 'react';

/** The severity rows' shape, so every row in and out of the popover lines up with them. */
const ROW = 'flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors';

const COUNT = 'font-mono text-[11px] tabular-nums text-muted-foreground';

/**
 * Match the typed text anywhere in the assessment's name. cmdk's default is a
 * fuzzy score, which with a dozen similar names ("… Check", "… Validation")
 * lets a few letters match nearly everything.
 */
function matchName(_value: string, search: string, keywords?: string[]): number {
  const name = (keywords ?? []).join(' ').toLowerCase();
  return name.includes(search.trim().toLowerCase()) ? 1 : 0;
}

/** A checkbox drawn at the size of the severity dots, so it sits in their column. */
function Tick({ on }: { on: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        'flex size-3 shrink-0 items-center justify-center rounded-[3px] border',
        on ? 'border-foreground bg-foreground' : 'border-muted-foreground/50',
      )}
    >
      {on && <Check className="size-2.5 text-background" strokeWidth={3} />}
    </span>
  );
}

interface AssessmentFilterProps {
  /** Every assessment with issues in view, paired with its count, most issues first. */
  counts: [WorkflowRunType, number][];
  value: WorkflowRunType[];
  onChange: (value: WorkflowRunType[]) => void;
}

/**
 * Narrows the issues to a few assessments.
 *
 * A project can run a dozen or more assessments with long names, too many to
 * list in the rail beside the outline. The rail carries one row that opens the
 * full, searchable list beside it, and under that row the assessments already
 * picked, so an active filter is always in sight and one click from removal.
 * Everything is drawn as rail rows, so it reads as part of the filters above.
 */
export function AssessmentFilter({ counts, value, onChange }: AssessmentFilterProps) {
  const { getWorkflowTypeName } = useWorkflowTypes();
  const [open, setOpen] = useState(false);

  const countOf = new Map(counts);
  // A selected assessment can lose its last visible issue (say, once resolved
  // issues are hidden). Keep it listed so it can still be unpicked.
  const options: [WorkflowRunType, number][] = [
    ...counts,
    ...value.filter((type) => !countOf.has(type)).map((type): [WorkflowRunType, number] => [type, 0]),
  ];

  const toggle = (type: WorkflowRunType) =>
    onChange(value.includes(type) ? value.filter((t) => t !== type) : [...value, type]);

  return (
    <div className="space-y-px">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button aria-label="Filter by assessment" className={cn(ROW, open ? RAIL_ITEM_ACTIVE : RAIL_ITEM_IDLE)}>
            <ListFilter className="size-3 shrink-0 text-muted-foreground" aria-hidden />
            <span className="flex-1 text-left">Assessments</span>
            <span className={COUNT}>
              {value.length === 0 ? `All ${options.length}` : `${value.length} of ${options.length}`}
            </span>
            <ChevronRight className="-mr-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden />
          </button>
        </PopoverTrigger>
        <PopoverContent side="right" align="start" sideOffset={16} className="w-72 bg-sidebar p-0">
          <Command filter={matchName} className="bg-transparent">
            <CommandInput placeholder={`Find among ${options.length} assessments`} />
            <CommandList className="max-h-[min(24rem,60vh)]">
              <CommandEmpty className="px-4 py-3 text-left text-xs text-muted-foreground">
                No assessment matches.
              </CommandEmpty>
              <CommandGroup className="p-1.5">
                {options.map(([type, count]) => {
                  const on = value.includes(type);
                  const name = getWorkflowTypeName(type);
                  return (
                    <CommandItem
                      key={type}
                      value={type}
                      keywords={[name]}
                      onSelect={() => toggle(type)}
                      aria-checked={on}
                      title={name}
                      className={cn(
                        ROW,
                        'mt-px data-[selected=true]:bg-accent/40 data-[selected=true]:text-foreground',
                        on && `${RAIL_ITEM_ACTIVE} data-[selected=true]:bg-foreground/8`,
                      )}
                    >
                      <Tick on={on} />
                      <span className="min-w-0 flex-1 truncate">{name}</span>
                      <span className={COUNT}>{count}</span>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            </CommandList>
          </Command>
          {/* Outside Command: cmdk takes Enter anywhere inside it to select the
              highlighted item, which would swallow Enter on this button. */}
          {value.length > 0 && (
            <div className="flex items-center justify-between border-t px-3.5 py-2">
              <span className="text-xs text-muted-foreground">{value.length} selected</span>
              <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={() => onChange([])}>
                Clear
              </Button>
            </div>
          )}
        </PopoverContent>
      </Popover>

      {value.map((type) => (
        <button
          key={type}
          onClick={() => toggle(type)}
          aria-pressed
          title={`Stop filtering by ${getWorkflowTypeName(type)}`}
          className={cn(ROW, RAIL_ITEM_ACTIVE)}
        >
          <Tick on />
          <span className="min-w-0 flex-1 truncate text-left">{getWorkflowTypeName(type)}</span>
          <span className={COUNT}>{countOf.get(type) ?? 0}</span>
        </button>
      ))}
    </div>
  );
}
