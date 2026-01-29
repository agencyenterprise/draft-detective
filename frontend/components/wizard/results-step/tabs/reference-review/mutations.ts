import {
  addFilesToProjectApiProjectProjectIdFilesPost,
  addFileToProjectApiProjectProjectIdFilePost,
  deleteProjectFileEndpointApiProjectProjectIdFilesFileIdDelete,
  FileRole,
  startMultipleWorkflowsApiWorkflowsStartMultiplePost,
  startWorkflowApiWorkflowsStartPost,
  WorkflowRunType,
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

export interface UploadFileParams {
  file: File;
  openaiApiKey: string;
}

export function useUploadFileMutation(projectId: string, referenceId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ file, openaiApiKey }: UploadFileParams) => {
      await addFileToProjectApiProjectProjectIdFilePost({
        path: { project_id: projectId },
        body: { file, reference_id: referenceId },
      });
    },
    onSuccess: createOnSuccess(queryClient, projectId, 'File uploaded. Processing started.'),
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

export interface ReplaceFileParams {
  file: File;
  openaiApiKey: string;
}

export function useReplaceFileMutation(projectId: string, referenceId: string, existingFileId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ file, openaiApiKey }: ReplaceFileParams) => {
      // 1. Upload the new file
      await addFileToProjectApiProjectProjectIdFilePost({
        path: { project_id: projectId },
        body: { file, reference_id: referenceId },
      });

      // 2. Delete the existing file if present
      if (existingFileId) {
        await deleteProjectFileEndpointApiProjectProjectIdFilesFileIdDelete({
          path: { project_id: projectId, file_id: existingFileId },
        });
      }
    },
    onSuccess: createOnSuccess(queryClient, projectId, 'File replaced. Processing started.'),
    onError: createOnError('Failed to replace file'),
  });
}

export interface FetchFromWebParams {
  openaiApiKey: string;
}

export function useFetchFromWebMutation(projectId: string, referenceId: string, referenceText: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ openaiApiKey }: FetchFromWebParams) => {
      await startWorkflowApiWorkflowsStartPost({
        body: {
          type: 'reference_downloader',
          project_id: projectId,
          references: [{ reference_id: referenceId, text: referenceText }],
          openai_api_key: openaiApiKey || null,
        },
      });
    },
    onSuccess: createOnSuccess(queryClient, projectId, 'Reference fetch started'),
    onError: createOnError('Failed to start reference fetch'),
  });
}

export interface FetchAllFromWebParams {
  references: Array<{ reference_id: string; text: string }>;
  openaiApiKey: string;
}

export function useFetchAllFromWebMutation(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ references, openaiApiKey }: FetchAllFromWebParams) => {
      await startWorkflowApiWorkflowsStartPost({
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

export interface BatchUploadParams {
  files: File[];
  openaiApiKey: string;
}

export function useBatchUploadMutation(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ files, openaiApiKey }: BatchUploadParams) => {
      await addFilesToProjectApiProjectProjectIdFilesPost({
        path: { project_id: projectId },
        body: { files, role: FileRole.Support },
      });

      // 2. Start ReferenceFileMatching workflow to immediately match the new files to the references
      return startMultipleWorkflowsApiWorkflowsStartMultiplePost({
        body: {
          project_id: projectId,
          workflow_types: [WorkflowRunType.ReferenceFileMatching],
          openai_api_key: openaiApiKey || undefined,
        },
      });
    },
    onSuccess: createOnSuccess(queryClient, projectId, 'Files uploaded. Processing and matching workflows started.'),
    onError: createOnError('Failed to upload files'),
  });
}
