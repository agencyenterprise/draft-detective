import { useState } from 'react';
import { toast } from 'sonner';
import { isApiError } from '@/lib/api-error';

export interface FileDownloadMessages {
  loading: string;
  /** Shown under `loading` only: the result toast clears it. */
  description?: string;
  success: string;
  /** Shown when the server gives no reason of its own. */
  error: string;
}

/**
 * The server's reason for refusing a download, when it is one the user can act on. A 4xx names the
 * request's problem ("Project not found"); a 5xx's detail can carry an internal exception's text.
 */
function refusalReason(error: unknown): string | undefined {
  return isApiError(error) && error.status < 500 ? error.detail : undefined;
}

/**
 * Runs a download behind one toast: `loading` while `save` runs, then `success`, or on failure the
 * server's reason for refusing it (else `error`). `isDownloading` is true meanwhile.
 */
export function useFileDownload() {
  const [isDownloading, setIsDownloading] = useState(false);

  const download = async (save: () => Promise<void>, messages: FileDownloadMessages): Promise<void> => {
    setIsDownloading(true);
    const id = toast.loading(messages.loading, { description: messages.description });
    try {
      await save();
      // Sonner merges an update into the toast it replaces, so the loading description is cleared here.
      toast.success(messages.success, { id, description: null });
    } catch (error) {
      console.error(`${messages.error}:`, error);
      toast.error(refusalReason(error) || messages.error, { id, description: null });
    } finally {
      setIsDownloading(false);
    }
  };

  return { download, isDownloading };
}
