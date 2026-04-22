export interface AnalysisResultCardProps {
  title: string;
  children: React.ReactNode;
  id?: string;
}

export function AnalysisResultCard({ title, children, id }: AnalysisResultCardProps) {
  return (
    <div id={id} className="bg-card shadow-sm rounded-xl border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <p className="font-medium">{title}</p>
      </div>

      <div className="space-y-4">{children}</div>
    </div>
  );
}
