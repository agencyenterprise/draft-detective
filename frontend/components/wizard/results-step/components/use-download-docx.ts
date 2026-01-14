import { useState } from 'react';
import { toast } from 'sonner';
import { downloadProjectDocxApiProjectsProjectIdDocxDownloadGet } from '@/lib/generated-api';
import { downloadFile } from '@/lib/file-download';

interface UseDownloadDocxOptions {
  projectId: string;
  shareToken?: string | null;
}

export async function downloadDocxFile(projectId: string, shareToken?: string | null): Promise<void> {
  const response = await downloadProjectDocxApiProjectsProjectIdDocxDownloadGet({
    path: { project_id: projectId },
    query: shareToken ? { share_token: shareToken } : undefined,
  });

  if (!(response instanceof Blob)) {
    throw new Error('Unexpected response type from DOCX download');
  }

  const timestamp = new Date().toISOString().split('T')[0];
  const filename = `document_${projectId}_${timestamp}.docx`;

  downloadFile({ blob: response, filename });
}

export function useDownloadDocx({ projectId, shareToken }: UseDownloadDocxOptions) {
  const [isDownloading, setIsDownloading] = useState(false);

  const download = async (includeShareLinks: boolean = false) => {
    setIsDownloading(true);

    const loadingMessage = includeShareLinks ? 'Preparing DOCX with share links...' : 'Preparing DOCX for download...';

    const toastId = toast.loading(loadingMessage, {
      description: 'This may take a few moments',
    });

    try {
      const tokenToUse = includeShareLinks ? shareToken : null;
      await downloadDocxFile(projectId, tokenToUse);
      toast.success('DOCX file downloaded successfully', { id: toastId, description: null });
    } catch (error) {
      console.error('Failed to download docx:', error);
      toast.error('Failed to download DOCX file', { id: toastId, description: null });
    } finally {
      setIsDownloading(false);
    }
  };

  return { download, isDownloading };
}
