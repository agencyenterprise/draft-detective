'use client';

import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { ClaimSubstantiatorStateSummary } from '@/lib/generated-api';
import { workflowsApi } from '@/lib/api';
import { Download } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

interface DownloadDocxButtonProps {
  workflowRunId: string | undefined;
  results: ClaimSubstantiatorStateSummary | undefined;
}

export function DownloadDocxButton({ workflowRunId, results }: DownloadDocxButtonProps) {
  const [isDownloading, setIsDownloading] = useState(false);

  // Only show button if original file was a .docx
  const hasDocx = results?.file?.originalFilePath?.endsWith('.docx');

  const handleDownload = async () => {
    if (!workflowRunId) return;

    setIsDownloading(true);
    try {
      const response = await workflowsApi.downloadDocxApiWorkflowRunsWorkflowRunIdDocxDownloadGet({
        workflowRunId,
      });

      const blob = await response.raw.blob();
      const contentDisposition = response.raw.headers.get('content-disposition');
      const filenameMatch = contentDisposition?.match(/filename="?(.+?)"?$/);
      const filename = filenameMatch?.[1] || `document_${workflowRunId}.docx`;

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

  // Don't render if no docx file
  if (!hasDocx) {
    return null;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button onClick={handleDownload} disabled={isDownloading} variant="outline" size="icon">
          <Download className="h-4 w-4" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        <p>{isDownloading ? 'Downloading...' : 'Download DOCX'}</p>
      </TooltipContent>
    </Tooltip>
  );
}
