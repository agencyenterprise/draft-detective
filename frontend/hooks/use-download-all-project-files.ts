import { toast } from 'sonner';
import { downloadAllProjectFilesApiProjectProjectIdFilesDownloadAllGet, FileRole } from '@/lib/generated-api';
import { useShare } from '@/context/share-context';
import { type FileResponse, saveFileResponse } from '@/lib/file-download';
import { useFileDownload } from '@/lib/hooks/use-file-download';

/** Every caller names its roles: the files tab wants every uploaded role, the references tabs only sources. */
export function useDownloadAllProjectFiles(projectId: string | null | undefined, roles: FileRole[]) {
  const { shareToken } = useShare();
  const { download, isDownloading } = useFileDownload();

  const downloadAll = async () => {
    if (!projectId) {
      toast.error('Project ID is required to download files');
      return;
    }

    await download(
      async () => {
        const file = (await downloadAllProjectFilesApiProjectProjectIdFilesDownloadAllGet({
          path: { project_id: projectId },
          query: { roles, share_token: shareToken },
          responseStyle: 'fields',
        })) as unknown as FileResponse;
        saveFileResponse(file, `project_${projectId}_files.zip`);
      },
      {
        loading: 'Preparing download...',
        success: 'All files downloaded successfully',
        error: 'Failed to download files',
      },
    );
  };

  return { downloadAll, isDownloading };
}
