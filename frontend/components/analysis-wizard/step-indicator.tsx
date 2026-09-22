'use client';

import { cn } from '@/lib/utils';
import { Check } from 'lucide-react';

interface Step {
  label: string;
  completed: boolean;
}

interface StepIndicatorProps {
  currentStep: number;
  steps: Step[];
  className?: string;
}

/**
 * Where you are in the wizard, small enough to sit in a toolbar row: a numbered
 * dot and a label per step, joined by a hairline. The step you are on and the
 * ones behind you are in the primary colour; the rest wait in grey.
 */
export function StepIndicator({ currentStep, steps, className }: StepIndicatorProps) {
  return (
    <ol className={cn('flex items-center', className)} aria-label="Steps">
      {steps.map((step, index) => {
        const stepNumber = index + 1;
        const isActive = stepNumber === currentStep;
        const isCompleted = step.completed;
        const isLast = index === steps.length - 1;

        return (
          <li key={step.label} className="flex items-center" aria-current={isActive ? 'step' : undefined}>
            <span className="flex items-center gap-2">
              <span
                className={cn(
                  'flex size-5 shrink-0 items-center justify-center rounded-full font-mono text-[10px] transition-colors',
                  isCompleted || isActive ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground',
                )}
              >
                {isCompleted ? <Check className="size-3" /> : stepNumber}
              </span>
              <span
                className={cn(
                  'text-xs whitespace-nowrap transition-colors',
                  isActive ? 'font-medium text-foreground' : 'text-muted-foreground',
                )}
              >
                {step.label}
              </span>
            </span>

            {!isLast && (
              <span
                aria-hidden
                className={cn('mx-3 h-px w-8 transition-colors', step.completed ? 'bg-primary' : 'bg-border')}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
