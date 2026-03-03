import { useState } from 'react';
import { toast } from 'sonner';
import {
  downloadProjectDocxApiProjectsProjectIdDocxDownloadGet,
  DocxManipulatorType,
  SeverityEnum,
  WorkflowRunType,
} from '@/lib/generated-api';
import { downloadFile } from '@/lib/file-download';

export type DocxType = DocxManipulatorType | 'original';

interface UseDownloadDocxOptions {
  projectId: string;
  shareToken?: string | null;
  severities?: SeverityEnum[];
  workflowTypes?: WorkflowRunType[];
  includePassing?: boolean;
  docxType?: DocxType;
}

export async function downloadDocxFile(
  projectId: string,
  shareToken?: string | null,
  severities?: SeverityEnum[],
  workflowTypes?: WorkflowRunType[],
  docxType?: DocxType,
  includePassing?: boolean,
): Promise<void> {
  const response = await downloadProjectDocxApiProjectsProjectIdDocxDownloadGet({
    path: { project_id: projectId },
    query: {
      share_token: shareToken,
      severities: severities,
      workflow_types: workflowTypes,
      docx_type: docxType ?? 'original',
      include_passing: includePassing ?? false,
    },
  });

  if (!(response instanceof Blob)) {
    throw new Error('Unexpected response type from DOCX download');
  }

  const timestamp = new Date().toISOString().split('T')[0];
  const filename = `document_${projectId}_${timestamp}.docx`;

  downloadFile({ blob: response, filename });
}

export function useDownloadDocx({
  projectId,
  shareToken,
  severities,
  workflowTypes,
  includePassing,
  docxType: initialDocxType,
}: UseDownloadDocxOptions) {
  const [isDownloading, setIsDownloading] = useState(false);

  const download = async (docxType?: DocxType) => {
    setIsDownloading(true);

    const dType = docxType ?? initialDocxType ?? 'original';
    const loadingMessage =
      dType === 'add-in'
        ? 'Preparing DOCX for AI Reviewer Add-In...'
        : dType === 'comments-with-links'
          ? 'Preparing DOCX with share links...'
          : 'Preparing DOCX for download...';

    const toastId = toast.loading(loadingMessage, {
      description: 'This may take a few moments',
    });

    try {
      await downloadDocxFile(projectId, shareToken, severities, workflowTypes, dType, includePassing);
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
