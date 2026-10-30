import { useState } from 'react';
import { toast } from 'sonner';
import {
  downloadProjectDocxApiProjectsProjectIdDocxDownloadGet,
  DocxManipulatorType,
  SeverityEnum,
  WorkflowRunType,
} from '@/lib/generated-api';
import { downloadFile, filenameFromContentDisposition } from '@/lib/file-download';

export type DocxType = DocxManipulatorType | 'original';

/** What the export covers. Named rather than positional: there are too many. */
export interface DownloadDocxRequest {
  projectId: string;
  shareToken?: string | null;
  severities?: SeverityEnum[];
  workflowTypes?: WorkflowRunType[];
  docxType: DocxType;
  includePassing?: boolean;
  includeEdits: boolean;
  /**
   * Which revision to export. The app can have an earlier revision open, and
   * the file, its issues and the counts the dialog showed have to agree, so
   * whatever the user is looking at is what gets exported. Omitted means the
   * project's current revision.
   */
  revision?: number;
}

/** The same request, less `docxType` and `includeEdits`, which `download()` takes per call. */
type UseDownloadDocxOptions = Omit<DownloadDocxRequest, 'docxType' | 'includeEdits'>;

export async function downloadDocxFile({
  projectId,
  shareToken,
  severities,
  workflowTypes,
  docxType,
  includePassing,
  includeEdits,
  revision,
}: DownloadDocxRequest): Promise<void> {
  // 'fields' rather than the SDK's 'data', for the response headers: the backend
  // names the file after the uploaded document, and that name is what people
  // track the file by once it leaves the app.
  const { data, response } = (await downloadProjectDocxApiProjectsProjectIdDocxDownloadGet({
    path: { project_id: projectId },
    query: {
      share_token: shareToken,
      severities: severities,
      workflow_types: workflowTypes,
      docx_type: docxType,
      include_passing: includePassing ?? false,
      include_edits: includeEdits,
      revision: revision,
    },
    responseStyle: 'fields',
  })) as unknown as { data: unknown; response: Response };

  if (!(data instanceof Blob)) {
    throw new Error('Unexpected response type from DOCX download');
  }

  const timestamp = new Date().toISOString().split('T')[0];
  const filename =
    filenameFromContentDisposition(response.headers.get('content-disposition')) ??
    `document_${projectId}_${timestamp}.docx`;

  downloadFile({ blob: data, filename });
}

export function useDownloadDocx({
  projectId,
  shareToken,
  severities,
  workflowTypes,
  includePassing,
  revision,
}: UseDownloadDocxOptions) {
  const [isDownloading, setIsDownloading] = useState(false);

  const download = async (docxType: DocxType, includeEdits: boolean) => {
    setIsDownloading(true);

    const loadingMessage =
      docxType === 'comments-with-links' ? 'Preparing DOCX with share links...' : 'Preparing DOCX for download...';

    const toastId = toast.loading(loadingMessage, {
      description: 'This may take a few moments',
    });

    try {
      await downloadDocxFile({
        projectId,
        shareToken,
        severities,
        workflowTypes,
        docxType,
        includePassing,
        includeEdits,
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
