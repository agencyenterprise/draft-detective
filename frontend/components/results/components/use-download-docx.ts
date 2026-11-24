import {
  downloadProjectDocxApiProjectsProjectIdDocxDownloadGet,
  DocxManipulatorType,
  SeverityEnum,
  WorkflowRunType,
} from '@/lib/generated-api';
import { type FileResponse, saveFileResponse } from '@/lib/file-download';
import { type FileDownloadMessages, useFileDownload } from '@/lib/hooks/use-file-download';

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
  const file = (await downloadProjectDocxApiProjectsProjectIdDocxDownloadGet({
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
  })) as unknown as FileResponse;

  const timestamp = new Date().toISOString().split('T')[0];
  saveFileResponse(file, `document_${projectId}_${timestamp}.docx`);
}

/** The toasts of a DOCX export, wherever it starts. */
export function docxDownloadMessages(docxType: DocxType): FileDownloadMessages {
  return {
    loading:
      docxType === 'comments-with-links' ? 'Preparing DOCX with share links...' : 'Preparing DOCX for download...',
    description: 'This may take a few moments',
    success: 'DOCX file downloaded successfully',
    error: 'Failed to download DOCX file',
  };
}

export function useDownloadDocx(options: UseDownloadDocxOptions) {
  const { download: run, isDownloading } = useFileDownload();

  const download = (docxType: DocxType, includeEdits: boolean) =>
    run(() => downloadDocxFile({ ...options, docxType, includeEdits }), docxDownloadMessages(docxType));

  return { download, isDownloading };
}
