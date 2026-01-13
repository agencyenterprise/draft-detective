'use client';

import * as React from 'react';
import * as CheckboxPrimitive from '@radix-ui/react-checkbox';
import { CheckIcon, FlaskConical, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import { WorkflowTypeDescription } from '@/lib/generated-api';
import { Badge } from '../ui/badge';

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
  return (
    <label
      htmlFor={workflowType.type}
      className={cn(
        'rounded-lg p-4 cursor-pointer hover:bg-accent/50 transition-all block space-y-1',
        'border',
        checked ? 'border-primary border-1' : '',
        disabled && 'cursor-not-allowed opacity-50',
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2 flex-1">
          <CheckboxPrimitive.Root
            id={workflowType.type}
            checked={checked}
            onCheckedChange={onCheckedChange}
            disabled={disabled}
            data-slot="checkbox"
            className={cn(
              'peer border-input dark:bg-input/30 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground dark:data-[state=checked]:bg-primary data-[state=checked]:border-primary focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive size-4 shrink-0 rounded-[4px] border shadow-xs transition-shadow outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50',
            )}
          >
            <CheckboxPrimitive.Indicator
              data-slot="checkbox-indicator"
              className="flex items-center justify-center text-current transition-none"
            >
              <CheckIcon className="size-3.5" />
            </CheckboxPrimitive.Indicator>
          </CheckboxPrimitive.Root>
          <span className={cn('text-sm font-medium leading-none select-none', disabled && 'opacity-70')}>
            {workflowType.name}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {workflowType.is_experimental && (
            <Badge variant="secondary" className="flex items-center gap-1 text-xs shrink-0">
              <FlaskConical className="size-3" />
              Experimental
            </Badge>
          )}
          {workflowType.needs_web_search && (
            <Badge variant="outline" className="flex items-center gap-1 text-xs shrink-0">
              <Search className="size-3" />
              Performs Web Search
            </Badge>
          )}
        </div>
      </div>
      <p className="text-sm text-muted-foreground pl-6">{workflowType.description}</p>
    </label>
  );
}
