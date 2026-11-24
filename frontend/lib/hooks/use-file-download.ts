import { useState } from 'react';
import { toast } from 'sonner';
import { getErrorDetail } from '@/lib/api-error';

export interface FileDownloadMessages {
  loading: string;
  /** Shown under `loading` only: the result toast clears it. */
  description?: string;
  success: string;
  /** Shown when the server gives no reason of its own. */
  error: string;
}

/**
 * Runs a download behind one toast: `loading` while `save` runs, then `success`, or on failure the
 * server's reason (else `error`). `isDownloading` is true meanwhile.
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
      toast.error(getErrorDetail(error, messages.error), { id, description: null });
    } finally {
      setIsDownloading(false);
    }
  };

  return { download, isDownloading };
}
