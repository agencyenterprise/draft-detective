/**
 * Mutation hooks for reference review operations.
 *
 * File uploads are now handled via chunked resumable uploads in FileUploadDialog.
 * These mutations handle non-upload operations (remove, fetch from web).
 */

import {
  deleteProjectFileEndpointApiProjectProjectIdFilesFileIdDelete,
  startWorkflowApiWorkflowsStartPost,
} from '@/lib/generated-api';
import { useProjectMutation } from '@/lib/hooks/use-project-mutation';

export function useRemoveFileMutation(projectId: string, fileId: string | undefined) {
  return useProjectMutation(projectId, {
    mutationFn: async () => {
      if (!fileId) return Promise.resolve();
      return deleteProjectFileEndpointApiProjectProjectIdFilesFileIdDelete({
        path: { project_id: projectId, file_id: fileId },
      });
    },
    successMessage: 'File removed successfully',
    errorMessage: 'Failed to remove file',
  });
}

export function useFetchFromWebMutation(projectId: string, referenceId: string, referenceText: string) {
  return useProjectMutation(projectId, {
    mutationFn: async () => {
      await startWorkflowApiWorkflowsStartPost({
        body: {
          type: 'reference_downloader',
          project_id: projectId,
          references: [{ reference_id: referenceId, text: referenceText }],
        },
      });
    },
    successMessage: 'Reference fetch started',
    errorMessage: 'Failed to start reference fetch',
  });
}

export interface FetchAllFromWebParams {
  references: Array<{ reference_id: string; text: string }>;
}

export function useFetchAllFromWebMutation(projectId: string) {
  return useProjectMutation(projectId, {
    mutationFn: async ({ references }: FetchAllFromWebParams) => {
      await startWorkflowApiWorkflowsStartPost({
        body: {
          type: 'reference_downloader',
          project_id: projectId,
          references: references,
        },
      });
    },
    successMessage: 'Reference fetch started',
    errorMessage: 'Failed to start reference fetch',
  });
}
