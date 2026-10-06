import { getErrorMessage } from '@/lib/api-error';
import { AlertTriangle, Loader2 } from 'lucide-react';

/** What a tab shows while the data it fetches for itself is on its way. */
export function TabLoading({ label }: { label: string }) {
  return (
    <div className="flex h-full items-center justify-center p-8" role="status">
      <Loader2 className="mr-2 size-4 animate-spin text-muted-foreground" />
      <span className="text-sm text-muted-foreground">{label}</span>
    </div>
  );
}

/**
 * What a tab shows when a request it depends on failed. Said outright, so a
 * failed fetch never reads as an empty result or as a request still running.
 */
export function TabError({ what, error }: { what: string; error: unknown }) {
  return (
    <div className="flex h-full items-center justify-center p-8" role="alert">
      <AlertTriangle className="mr-2 size-4 shrink-0 text-destructive" />
      <span className="text-sm text-destructive">
        Could not load {what}: {getErrorMessage(error, 'unknown error')}
      </span>
    </div>
  );
}
