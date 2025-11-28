import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { ClaimSubstantiatorStateSummary } from '@/lib/generated-api';
import { workflowsApi } from '@/lib/api';
import { Download, EllipsisVerticalIcon, FileTextIcon, RefreshCcwIcon } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

export interface AnalysisOptionsMenuProps {
  onSaveAsEvalTest: () => void;
  onReevaluate: () => void;
  workflowRunId: string | null | undefined;
  results: ClaimSubstantiatorStateSummary | undefined;
}

export function AnalysisOptionsMenu({
  onSaveAsEvalTest,
  onReevaluate,
  workflowRunId,
  results,
}: AnalysisOptionsMenuProps) {
  const [isDownloading, setIsDownloading] = useState(false);
  const hasDocx = results?.file?.originalFilePath?.endsWith('.docx');

  const handleDownloadDocx = async () => {
    if (!workflowRunId) return;

    setIsDownloading(true);
    try {
      const response = await workflowsApi.downloadDocxApiWorkflowRunsWorkflowRunIdDocxDownloadGetRaw({
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

  return (
    <DropdownMenu>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <EllipsisVerticalIcon />
            </Button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent>
          <p>See more options for this analysis</p>
        </TooltipContent>
      </Tooltip>
      <DropdownMenuContent className="w-56">
        <Tooltip>
          <TooltipTrigger asChild>
            <DropdownMenuItem className="cursor-pointer" onClick={onSaveAsEvalTest}>
              <FileTextIcon />
              Save as eval test
            </DropdownMenuItem>
          </TooltipTrigger>
          <TooltipContent side="left">
            <p>Generate evaluation test cases from these results for testing agents</p>
          </TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <DropdownMenuItem className="cursor-pointer" onClick={onReevaluate}>
              <RefreshCcwIcon />
              Re-run analysis
            </DropdownMenuItem>
          </TooltipTrigger>
          <TooltipContent side="left">
            <p>Re-run the analysis with different agents/configuration</p>
          </TooltipContent>
        </Tooltip>
        {hasDocx && (
          <Tooltip>
            <TooltipTrigger asChild>
              <DropdownMenuItem className="cursor-pointer" onClick={handleDownloadDocx} disabled={isDownloading}>
                <Download />
                {isDownloading ? 'Downloading...' : 'Download DOCX'}
              </DropdownMenuItem>
            </TooltipTrigger>
            <TooltipContent side="left">
              <p>Download the original or reviewed DOCX file</p>
            </TooltipContent>
          </Tooltip>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
