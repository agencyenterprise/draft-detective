'use client';

import * as React from 'react';
import * as CheckboxPrimitive from '@radix-ui/react-checkbox';
import { CheckIcon, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CheckboxWithDescriptionProps {
  id: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
  description: string;
  /** Shown before the label, the same icon the feature carries elsewhere. */
  icon?: LucideIcon;
  bordered?: boolean;
  disabled?: boolean;
}

export function CheckboxWithDescription({
  id,
  checked,
  onCheckedChange,
  label,
  description,
  icon: Icon,
  bordered = false,
  disabled = false,
}: CheckboxWithDescriptionProps) {
  return (
    <label
      htmlFor={id}
      className={cn(
        'rounded-lg p-4 cursor-pointer hover:bg-accent/50 transition-all block space-y-1',
        bordered && 'border',
        checked && bordered ? 'border-primary border-1' : '',
        disabled && 'cursor-not-allowed opacity-50',
      )}
    >
      <div className="flex items-center space-x-2">
        <CheckboxPrimitive.Root
          id={id}
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
        {Icon && <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />}
        <span className={cn('text-sm font-medium leading-none select-none', disabled && 'opacity-70')}>{label}</span>
      </div>
      <p className="text-sm text-muted-foreground pl-6">{description}</p>
    </label>
  );
}
