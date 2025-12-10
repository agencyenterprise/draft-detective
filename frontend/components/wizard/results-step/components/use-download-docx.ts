import { downloadProjectDocxApiProjectsProjectIdDocxDownloadGet } from '@/lib/generated-api';
import { useState } from 'react';
import { toast } from 'sonner';

export function useDownloadDocx(projectId: string) {
  const [isDownloading, setIsDownloading] = useState(false);

  const download = async () => {
    setIsDownloading(true);
    try {
      const { response, data: blob } = (await downloadProjectDocxApiProjectsProjectIdDocxDownloadGet({
        path: { project_id: projectId },
        responseStyle: 'fields',
      })) as { response: Response; data: Blob };

      const contentDisposition = response.headers.get('content-disposition');
      const filenameMatch = contentDisposition?.match(/filename="?(.+?)"?$/);
      const filename = filenameMatch?.[1] || `document_${projectId}.docx`;

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      toast.success('DOCX file downloaded successfully');
    } catch (error) {
      console.error('Failed to download docx:', error);
      toast.error('Failed to download DOCX file');
    } finally {
      setIsDownloading(false);
    }
  };

  return { download, isDownloading };
}
