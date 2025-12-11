import { useState } from 'react';
import { toast } from 'sonner';
import { downloadAllProjectFilesApiProjectProjectIdFilesDownloadAllGet } from '@/lib/generated-api';

export function useDownloadAllProjectFiles(projectId: string | null | undefined) {
  const [isDownloading, setIsDownloading] = useState(false);

  const downloadAll = async () => {
    if (!projectId) {
      toast.error('Project ID is required to download files');
      return;
    }

    setIsDownloading(true);
    try {
      const { response, data: blob } = (await downloadAllProjectFilesApiProjectProjectIdFilesDownloadAllGet({
        path: { project_id: projectId },
        responseStyle: 'fields',
      })) as { response: Response; data: Blob };

      const contentDisposition = response.headers.get('content-disposition');
      const filenameMatch = contentDisposition?.match(/filename="?(.+?)"?$/);
      const filename = filenameMatch?.[1] || `project_${projectId}_files.zip`;

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      toast.success('All files downloaded successfully');
    } catch (error) {
      console.error('Failed to download files:', error);
      toast.error('Failed to download files');
    } finally {
      setIsDownloading(false);
    }
  };

  return { downloadAll, isDownloading };
}
