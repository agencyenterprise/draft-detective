import { cn } from '@/lib/utils';

export interface LabeledValueProps {
  label: string;
  children: React.ReactNode;
  labelWrap?: boolean;
  className?: string;
}

export function LabeledValue({ label, labelWrap = false, children, className }: LabeledValueProps) {
  return (
    <div className={className}>
      <div className={cn('font-medium', !labelWrap && 'inline')}>{label}:</div>{' '}
      <div className={cn('text-foreground', !labelWrap && 'inline')}>{children}</div>
    </div>
  );
}
