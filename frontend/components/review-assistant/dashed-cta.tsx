import { LucideIcon } from 'lucide-react';
import { ReactNode } from 'react';

/** The dashed call-to-action box the Peer Review steps use while they have nothing to show. */
export function DashedCta({
  icon: Icon,
  title,
  description,
  action,
  spin = false,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  spin?: boolean;
}) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-md border border-dashed px-6 py-10 text-center">
      <Icon className={spin ? 'size-7 animate-spin text-muted-foreground' : 'size-7 text-muted-foreground'} />
      <div className="space-y-1.5">
        <p className="text-sm font-medium">{title}</p>
        {description && (
          <p className="mx-auto max-w-prose text-[13px] leading-relaxed text-muted-foreground">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}
