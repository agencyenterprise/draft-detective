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
import { QueryClient, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

// Helper function builders for common callbacks
function createOnSuccess(queryClient: QueryClient, projectId: string, message: string) {
  return () => {
    queryClient.invalidateQueries({ queryKey: ['project', projectId] });
    toast.success(message);
  };
}

function createOnError(fallbackMessage: string) {
  return (error: Error) => {
    toast.error(error instanceof Error ? error.message : fallbackMessage);
  };
}

export function useRemoveFileMutation(projectId: string, fileId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      if (!fileId) return Promise.resolve();
      return deleteProjectFileEndpointApiProjectProjectIdFilesFileIdDelete({
        path: { project_id: projectId, file_id: fileId },
      });
    },
    onSuccess: createOnSuccess(queryClient, projectId, 'File removed successfully'),
    onError: createOnError('Failed to remove file'),
  });
}

export function useFetchFromWebMutation(projectId: string, referenceId: string, referenceText: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      await startWorkflowApiWorkflowsStartPost({
        body: {
          type: 'reference_downloader',
          project_id: projectId,
          references: [{ reference_id: referenceId, text: referenceText }],
        },
      });
    },
    onSuccess: createOnSuccess(queryClient, projectId, 'Reference fetch started'),
    onError: createOnError('Failed to start reference fetch'),
  });
}

export interface FetchAllFromWebParams {
  references: Array<{ reference_id: string; text: string }>;
}

export function useFetchAllFromWebMutation(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ references }: FetchAllFromWebParams) => {
      await startWorkflowApiWorkflowsStartPost({
        body: {
          type: 'reference_downloader',
          project_id: projectId,
          references: references,
        },
      });
    },
    onSuccess: createOnSuccess(queryClient, projectId, 'Reference fetch started'),
    onError: createOnError('Failed to start reference fetch'),
  });
}
