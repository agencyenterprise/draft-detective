import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

/** A keyboard shortcut hint beside a label, in the explorer's issue-stepper style. */
export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        'hidden rounded border border-current/30 px-1 font-mono text-[10px] uppercase opacity-80 sm:inline-block',
        className,
      )}
    >
      {children}
    </kbd>
  );
}
