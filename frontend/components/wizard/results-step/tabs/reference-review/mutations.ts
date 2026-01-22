import {
  deleteProjectFileEndpointApiProjectProjectIdFilesFileIdDelete,
  startWorkflowApiWorkflowsStartPost,
  uploadProjectFileEndpointApiProjectProjectIdFilePost,
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

export function useUploadFileMutation(projectId: string, referenceIndex: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (file: File) => {
      return uploadProjectFileEndpointApiProjectProjectIdFilePost({
        path: { project_id: projectId },
        body: { file, reference_index: referenceIndex },
      });
    },
    onSuccess: createOnSuccess(queryClient, projectId, 'File uploaded successfully'),
    onError: createOnError('Failed to upload file'),
  });
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

export function useReplaceFileMutation(projectId: string, referenceIndex: number, existingFileId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (file: File) => {
      await uploadProjectFileEndpointApiProjectProjectIdFilePost({
        path: { project_id: projectId },
        body: { file, reference_index: referenceIndex },
      });

      if (existingFileId) {
        await deleteProjectFileEndpointApiProjectProjectIdFilesFileIdDelete({
          path: { project_id: projectId, file_id: existingFileId },
        });
      }
    },
    onSuccess: createOnSuccess(queryClient, projectId, 'File replaced successfully'),
    onError: createOnError('Failed to replace file'),
  });
}

export function useFetchFromWebMutation(projectId: string, referenceIndex: number, referenceText: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      return startWorkflowApiWorkflowsStartPost({
        body: {
          type: 'reference_downloader',
          project_id: projectId,
          references: [{ index: referenceIndex, text: referenceText }],
        },
      });
    },
    onSuccess: createOnSuccess(queryClient, projectId, 'Reference fetch started'),
    onError: createOnError('Failed to start reference fetch'),
  });
}

export interface FetchAllFromWebParams {
  references: Array<{ index: number; text: string }>;
  openaiApiKey: string;
}

export function useFetchAllFromWebMutation(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ references, openaiApiKey }: FetchAllFromWebParams) => {
      return startWorkflowApiWorkflowsStartPost({
        body: {
          type: 'reference_downloader',
          project_id: projectId,
          references: references,
          openai_api_key: openaiApiKey || null,
        },
      });
    },
    onSuccess: createOnSuccess(queryClient, projectId, 'Reference fetch started'),
    onError: createOnError('Failed to start reference fetch'),
  });
}
