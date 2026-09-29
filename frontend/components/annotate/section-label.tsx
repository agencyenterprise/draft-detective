import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

/** The small mono caps heading the explorer's rails use for their sections. */
export function SectionLabel({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <h3 className={cn('font-mono text-[10px] tracking-wide text-muted-foreground uppercase', className)}>{children}</h3>
  );
}
