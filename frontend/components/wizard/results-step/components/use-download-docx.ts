import { projectsApi } from '@/lib/api';
import { useState } from 'react';
import { toast } from 'sonner';

interface UseDownloadDocxOptions {
  projectId: string;
  shareToken?: string | null;
}

async function downloadDocxFile(projectId: string, shareToken?: string | null): Promise<void> {
  const response = await projectsApi.downloadProjectDocxApiProjectsProjectIdDocxDownloadGetRaw({
    projectId,
    shareToken: shareToken ?? undefined,
  });

  const blob = await response.raw.blob();
  const contentDisposition = response.raw.headers.get('content-disposition');
  const filenameMatch = contentDisposition?.match(/filename="?(.+?)"?$/);
  const filename = filenameMatch?.[1] || `document_${projectId}.docx`;

  const blobUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(blobUrl);
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
      toast.success('DOCX file downloaded successfully', { id: toastId });
    } catch (error) {
      console.error('Failed to download docx:', error);
      toast.error('Failed to download DOCX file', { id: toastId });
    } finally {
      setIsDownloading(false);
    }
  };

  return { download, isDownloading };
}
