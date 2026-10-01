import { Loader2 } from 'lucide-react';

/** What a tab shows while the data it fetches for itself is on its way. */
export function TabLoading({ label }: { label: string }) {
  return (
    <div className="flex h-full items-center justify-center p-8" role="status">
      <Loader2 className="mr-2 size-4 animate-spin text-muted-foreground" />
      <span className="text-sm text-muted-foreground">{label}</span>
    </div>
  );
}
