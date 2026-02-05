import { useState, useCallback, useRef, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  uploadFile,
  cancelUpload as cancelChunkedUpload,
  pauseUpload as pauseChunkedUpload,
  resumeUpload as resumeChunkedUpload,
  ChunkedUploadState,
  UploadProgress,
  isActiveStatus,
  createProgress,
} from '../services/chunked-upload';
import { FileRole, File as FileRecord } from '../generated-api';

// Derive from ChunkedUploadState, excluding internal implementation details
export type UploadFileState = Omit<ChunkedUploadState, 'sessionId' | 'abortController' | 'isPaused' | 'metadata'>;

export interface UseUploadOptions {
  projectId: string;
  fileRole?: FileRole;
  maxConcurrent?: number;
  onFileComplete?: (file: File, fileRecord: FileRecord) => void;
  onAllComplete?: (fileRecords: FileRecord[]) => void;
  onError?: (error: Error, fileName: string) => void;
}

export interface UseUploadReturn {
  files: UploadFileState[];
  isUploading: boolean;
  overallProgress: number;
  completedCount: number;
  totalCount: number;
  completedFiles: FileRecord[];
  addFiles: (files: File[]) => void;
  removeFile: (fileId: string) => void;
  startUpload: (filesToUpload?: File[]) => Promise<FileRecord[]>;
  pauseFile: (fileId: string) => void;
  resumeFile: (fileId: string) => Promise<void>;
  pauseAll: () => void;
  resumeAll: () => Promise<void>;
  cancelAll: () => void;
  reset: () => void;
}

const MAX_CONCURRENT_DEFAULT = 3;

export function useUpload(options: UseUploadOptions): UseUploadReturn {
  const {
    projectId,
    fileRole = FileRole.Support,
    maxConcurrent = MAX_CONCURRENT_DEFAULT,
    onFileComplete,
    onAllComplete,
    onError,
  } = options;

  const queryClient = useQueryClient();
  const [files, setFiles] = useState<UploadFileState[]>([]);
  const uploadsRef = useRef<Map<string, ChunkedUploadState>>(new Map());
  const completedFilesRef = useRef<FileRecord[]>([]);
  // Use ref to track file states during upload (avoids React state timing issues)
  const fileStatesRef = useRef<Map<string, UploadFileState>>(new Map());

  const syncToReactState = useCallback(() => {
    setFiles(Array.from(fileStatesRef.current.values()));
  }, []);

  const updateFileStateInternal = useCallback(
    (fileId: string, updates: Partial<UploadFileState>) => {
      const existing = fileStatesRef.current.get(fileId);
      if (existing) {
        fileStatesRef.current.set(fileId, { ...existing, ...updates });
        syncToReactState();
      }
    },
    [syncToReactState],
  );

  const createFileState = useCallback(
    (file: File): UploadFileState => ({
      id: `${projectId}-${file.name}-${Date.now()}-${Math.random()}`,
      file,
      status: 'pending',
      progress: createProgress(0, file.size),
    }),
    [projectId],
  );

  const addFiles = useCallback(
    (newFiles: File[]) => {
      newFiles.forEach((file) => {
        const fileState = createFileState(file);
        fileStatesRef.current.set(fileState.id, fileState);
      });
      syncToReactState();
    },
    [createFileState, syncToReactState],
  );

  const removeFile = useCallback(
    (fileId: string) => {
      const upload = uploadsRef.current.get(fileId);
      if (upload) {
        cancelChunkedUpload(upload);
        uploadsRef.current.delete(fileId);
      }
      fileStatesRef.current.delete(fileId);
      syncToReactState();
    },
    [syncToReactState],
  );

  const uploadSingleFile = useCallback(
    async (fileState: UploadFileState): Promise<FileRecord | null> => {
      try {
        const state = await uploadFile(
          fileState.file,
          { projectId, filename: fileState.file.name, fileRole },
          {
            onProgress: (progress) => {
              updateFileStateInternal(fileState.id, { status: 'uploading', progress });
            },
            onSuccess: (fileRecord) => {
              updateFileStateInternal(fileState.id, {
                status: 'completed',
                progress: createProgress(fileState.file.size, fileState.file.size),
                fileRecord,
              });
              uploadsRef.current.delete(fileState.id);
              onFileComplete?.(fileState.file, fileRecord);
              queryClient.invalidateQueries({ queryKey: ['project', projectId] });
            },
            onError: (error) => {
              updateFileStateInternal(fileState.id, { status: 'error', error: error.message });
              uploadsRef.current.delete(fileState.id);
              onError?.(error, fileState.file.name);
              toast.error(`Failed to upload ${fileState.file.name}: ${error.message}`);
            },
          },
        );

        uploadsRef.current.set(fileState.id, state);

        if (state.status === 'completed' && state.fileRecord) {
          return state.fileRecord;
        }
        return null;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Upload failed';
        updateFileStateInternal(fileState.id, { status: 'error', error: message });
        return null;
      }
    },
    [projectId, fileRole, onFileComplete, onError, queryClient, updateFileStateInternal],
  );

  const startUpload = useCallback(
    async (filesToUpload?: File[]): Promise<FileRecord[]> => {
      completedFilesRef.current = [];

      // Create file states and add to ref immediately
      let fileStates: UploadFileState[];
      if (filesToUpload && filesToUpload.length > 0) {
        fileStates = filesToUpload.map(createFileState);
        fileStates.forEach((fs) => fileStatesRef.current.set(fs.id, fs));
        syncToReactState();
      } else {
        fileStates = Array.from(fileStatesRef.current.values()).filter((f) => f.status === 'pending');
      }

      if (fileStates.length === 0) {
        return [];
      }

      // Process files in batches
      const results: (FileRecord | null)[] = [];
      for (let i = 0; i < fileStates.length; i += maxConcurrent) {
        const batch = fileStates.slice(i, i + maxConcurrent);
        const batchResults = await Promise.all(batch.map(uploadSingleFile));
        results.push(...batchResults);
      }

      const completedFiles = results.filter((r): r is FileRecord => r !== null);
      completedFilesRef.current = completedFiles;

      if (completedFiles.length > 0) {
        onAllComplete?.(completedFiles);
      }

      return completedFiles;
    },
    [maxConcurrent, uploadSingleFile, onAllComplete, createFileState, syncToReactState],
  );

  const pauseFile = useCallback(
    (fileId: string) => {
      const upload = uploadsRef.current.get(fileId);
      if (upload && upload.status === 'uploading') {
        pauseChunkedUpload(upload);
        updateFileStateInternal(fileId, { status: 'paused' });
      }
    },
    [updateFileStateInternal],
  );

  const resumeFile = useCallback(
    async (fileId: string) => {
      const upload = uploadsRef.current.get(fileId);
      if (!upload || upload.status !== 'paused') return;

      updateFileStateInternal(fileId, { status: 'uploading' });

      const updatedState = await resumeChunkedUpload(upload, {
        onProgress: (progress) => {
          updateFileStateInternal(fileId, { progress });
        },
        onSuccess: (fileRecord) => {
          updateFileStateInternal(fileId, {
            status: 'completed',
            progress: createProgress(upload.file.size, upload.file.size),
            fileRecord,
          });
          uploadsRef.current.delete(fileId);
          onFileComplete?.(upload.file, fileRecord);
          queryClient.invalidateQueries({ queryKey: ['project', projectId] });
        },
        onError: (error) => {
          updateFileStateInternal(fileId, { status: 'error', error: error.message });
          uploadsRef.current.delete(fileId);
          onError?.(error, upload.file.name);
          toast.error(`Failed to upload ${upload.file.name}: ${error.message}`);
        },
      });

      // Update state if paused again during resume
      if (updatedState.status === 'paused') {
        updateFileStateInternal(fileId, { status: 'paused' });
      }
    },
    [updateFileStateInternal, onFileComplete, onError, queryClient, projectId],
  );

  const pauseAll = useCallback(() => {
    uploadsRef.current.forEach((upload, fileId) => {
      if (upload.status === 'uploading') {
        pauseChunkedUpload(upload);
        updateFileStateInternal(fileId, { status: 'paused' });
      }
    });
  }, [updateFileStateInternal]);

  const resumeAll = useCallback(async () => {
    const pausedUploads = Array.from(uploadsRef.current.entries()).filter(([, upload]) => upload.status === 'paused');

    await Promise.all(pausedUploads.map(([fileId]) => resumeFile(fileId)));
  }, [resumeFile]);

  const cancelAll = useCallback(() => {
    uploadsRef.current.forEach((upload) => cancelChunkedUpload(upload));
    uploadsRef.current.clear();

    fileStatesRef.current.forEach((fs, id) => {
      if (isActiveStatus(fs.status) || fs.status === 'paused') {
        fileStatesRef.current.set(id, { ...fs, status: 'error', error: 'Cancelled' });
      }
    });
    syncToReactState();
  }, [syncToReactState]);

  const reset = useCallback(() => {
    cancelAll();
    fileStatesRef.current.clear();
    completedFilesRef.current = [];
    syncToReactState();
  }, [cancelAll, syncToReactState]);

  // Memoized derived state
  const isUploading = useMemo(() => files.some((f) => isActiveStatus(f.status)), [files]);

  const completedCount = useMemo(() => files.filter((f) => f.status === 'completed').length, [files]);

  const overallProgress = useMemo(
    () =>
      files.length > 0 ? Math.round(files.reduce((sum, f) => sum + f.progress.progress_percent, 0) / files.length) : 0,
    [files],
  );

  // Return copy of completedFiles to prevent external mutation
  const completedFiles = useMemo(() => [...completedFilesRef.current], [files]);

  return {
    files,
    isUploading,
    overallProgress,
    completedCount,
    totalCount: files.length,
    completedFiles,
    addFiles,
    removeFile,
    startUpload,
    pauseFile,
    resumeFile,
    pauseAll,
    resumeAll,
    cancelAll,
    reset,
  };
}
