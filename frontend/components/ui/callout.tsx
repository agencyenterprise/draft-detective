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
    container: 'bg-blue-50',
    border: 'border-blue-500',
    icon: 'text-blue-600',
    title: 'text-blue-900',
    content: 'text-blue-950',
  },
  warning: {
    container: 'bg-yellow-50',
    border: 'border-yellow-500',
    icon: 'text-yellow-600',
    title: 'text-yellow-900',
    content: 'text-yellow-950',
  },
  success: {
    container: 'bg-green-50',
    border: 'border-green-500',
    icon: 'text-green-600',
    title: 'text-green-900',
    content: 'text-green-950',
  },
  error: {
    container: 'bg-red-50',
    border: 'border-red-500',
    icon: 'text-red-600',
    title: 'text-red-900',
    content: 'text-red-950',
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
