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

export function StepIndicator({ currentStep, steps, className }: StepIndicatorProps) {
  return (
    <div className={cn('flex items-center justify-center gap-0', className)}>
      {steps.map((step, index) => {
        const stepNumber = index + 1;
        const isActive = stepNumber === currentStep;
        const isCompleted = step.completed;
        const isLast = index === steps.length - 1;

        return (
          <div
            key={step.label}
            className={cn(
              'flex items-center',
              stepNumber > 2 && 'animate-in fade-in slide-in-from-left-4 duration-300',
            )}
          >
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  'flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold transition-all duration-200',
                  isCompleted && 'bg-primary text-primary-foreground',
                  isActive && !isCompleted && 'bg-primary text-primary-foreground',
                  !isActive && !isCompleted && 'border-2 border-muted-foreground/30 text-muted-foreground',
                )}
              >
                {isCompleted ? <Check className="h-5 w-5" /> : stepNumber}
              </div>
              <span
                className={cn(
                  'mt-2 text-xs font-medium whitespace-nowrap transition-colors duration-200',
                  isActive || isCompleted ? 'text-foreground' : 'text-muted-foreground',
                )}
              >
                {step.label}
              </span>
            </div>

            {!isLast && (
              <div
                className={cn(
                  'mx-2 h-0.5 w-16 transition-all duration-300',
                  step.completed ? 'bg-primary' : 'bg-muted-foreground/30',
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
