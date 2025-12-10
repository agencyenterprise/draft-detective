import { SeverityEnum } from '@/lib/generated-api';
import { SeverityBadge } from './severity-badge';

export interface AnalysisResultCardProps {
  title: string;
  severity: SeverityEnum;
  children: React.ReactNode;
  id?: string;
}

export function AnalysisResultCard({ title, severity, children, id }: AnalysisResultCardProps) {
  return (
    <div id={id} className="bg-card shadow-sm rounded-xl border px-5 pb-5">
      <div className="flex items-center justify-between sticky pt-5 pb-3 -top-5 bg-background z-10">
        <p className="font-medium">{title}</p>

        <SeverityBadge severity={severity} />
      </div>

      <div className="space-y-4">{children}</div>
    </div>
  );
}
