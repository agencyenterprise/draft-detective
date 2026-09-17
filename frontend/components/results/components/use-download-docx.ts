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

/** What the export covers. Named rather than positional: there are too many. */
export interface DownloadDocxRequest {
  projectId: string;
  shareToken?: string | null;
  severities?: SeverityEnum[];
  workflowTypes?: WorkflowRunType[];
  docxType?: DocxType;
  includePassing?: boolean;
  includeEdits?: boolean;
  /**
   * Which revision to export. The app can have an earlier revision open, and
   * the file, its issues and the counts the dialog showed have to agree, so
   * whatever the user is looking at is what gets exported. Omitted means the
   * project's current revision.
   */
  revision?: number;
}

/** The same request, except `docxType` and `includeEdits` are only defaults here:
 *  `download()` takes either of them per call. */
type UseDownloadDocxOptions = DownloadDocxRequest;

export async function downloadDocxFile({
  projectId,
  shareToken,
  severities,
  workflowTypes,
  docxType,
  includePassing,
  includeEdits = true,
  revision,
}: DownloadDocxRequest): Promise<void> {
  const response = await downloadProjectDocxApiProjectsProjectIdDocxDownloadGet({
    path: { project_id: projectId },
    query: {
      share_token: shareToken,
      severities: severities,
      workflow_types: workflowTypes,
      docx_type: docxType ?? 'original',
      include_passing: includePassing ?? false,
      include_edits: includeEdits,
      revision: revision,
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
  revision,
  docxType: initialDocxType,
  includeEdits: initialIncludeEdits = true,
}: UseDownloadDocxOptions) {
  const [isDownloading, setIsDownloading] = useState(false);

  const download = async (docxType?: DocxType, includeEdits?: boolean) => {
    setIsDownloading(true);

    const dType = docxType ?? initialDocxType ?? 'original';
    const withEdits = includeEdits ?? initialIncludeEdits;
    const loadingMessage =
      dType === 'add-in'
        ? 'Preparing DOCX for Draft Detective Add-In...'
        : dType === 'comments-with-links'
          ? 'Preparing DOCX with share links...'
          : 'Preparing DOCX for download...';

    const toastId = toast.loading(loadingMessage, {
      description: 'This may take a few moments',
    });

    try {
      await downloadDocxFile({
        projectId,
        shareToken,
        severities,
        workflowTypes,
        docxType: dType,
        includePassing,
        includeEdits: withEdits,
        revision,
      });
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
