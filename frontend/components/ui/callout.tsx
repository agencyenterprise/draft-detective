import { cn } from '@/lib/utils';
import { LucideIcon } from 'lucide-react';
import { ReactNode } from 'react';

type CalloutVariant = 'info' | 'warning' | 'success' | 'error';

const variantStyles: Record<
  CalloutVariant,
  {
    container: string;
    border: string;
    icon: string;
    title: string;
    content: string;
  }
> = {
  info: {
    container: 'bg-blue-50 dark:bg-blue-950/40',
    border: 'border-blue-500 dark:border-blue-700',
    icon: 'text-blue-600 dark:text-blue-400',
    title: 'text-blue-900 dark:text-blue-200',
    content: 'text-blue-950 dark:text-blue-100',
  },
  warning: {
    container: 'bg-yellow-50 dark:bg-yellow-950/40',
    border: 'border-yellow-500 dark:border-yellow-700',
    icon: 'text-yellow-600 dark:text-yellow-400',
    title: 'text-yellow-900 dark:text-yellow-200',
    content: 'text-yellow-950 dark:text-yellow-100',
  },
  success: {
    container: 'bg-green-50 dark:bg-green-950/40',
    border: 'border-green-500 dark:border-green-700',
    icon: 'text-green-600 dark:text-green-400',
    title: 'text-green-900 dark:text-green-200',
    content: 'text-green-950 dark:text-green-100',
  },
  error: {
    container: 'bg-red-50 dark:bg-red-950/40',
    border: 'border-red-500 dark:border-red-700',
    icon: 'text-red-600 dark:text-red-400',
    title: 'text-red-900 dark:text-red-200',
    content: 'text-red-950 dark:text-red-100',
  },
};

export interface CalloutProps {
  title: string;
  children: ReactNode;
  variant?: CalloutVariant;
  icon?: LucideIcon;
  className?: string;
}

export function Callout({ title, children, variant = 'info', icon: Icon, className }: CalloutProps) {
  const styles = variantStyles[variant];

  return (
    <div
      className={cn('border-l-4 rounded-lg py-3 px-3 shadow-sm', styles.container, styles.border, className)}
      role="region"
      aria-label={title}
    >
      <div className="flex items-start gap-3">
        {Icon && <Icon className={cn('h-5 w-5 mt-0.5 flex-shrink-0', styles.icon)} />}
        <div className="flex-1 min-w-0 space-y-1">
          <h3 className={cn('font-semibold text-sm uppercase', styles.title)}>{title}</h3>
          <div className={cn('text-sm', styles.content)}>{children}</div>
        </div>
      </div>
    </div>
  );
}
