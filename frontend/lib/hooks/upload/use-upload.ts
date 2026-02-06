/**
 * React hook for managing multiple file uploads with progress tracking.
 * Used by file upload dialogs for supporting documents.
 */

import { useState, useCallback, useRef, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import Uppy from '@uppy/core';
import Tus from '@uppy/tus';
import { FileRole } from '../../generated-api';
import { UPLOAD_CONFIG, createTusOptions } from './config';
import type { UseUploadOptions, UseUploadReturn, UploadFileState, UploadStatus } from './types';
import { createProgress, isActiveStatus } from './types';

export function useUpload(options: UseUploadOptions): UseUploadReturn {
  const { projectId, fileRole = FileRole.Support, onFileComplete, onAllComplete, onError } = options;

  const queryClient = useQueryClient();
  const [files, setFiles] = useState<UploadFileState[]>([]);
  const uppyRef = useRef<Uppy | null>(null);
  const fileMapRef = useRef<Map<string, { file: File; state: UploadFileState }>>(new Map());

  // Refs for callbacks to get latest values in event handlers
  const callbackRefs = useRef({ onFileComplete, onAllComplete, onError });
  callbackRefs.current = { onFileComplete, onAllComplete, onError };

  const findUppyId = useCallback((fileId: string): string | undefined => {
    for (const [uppyId, entry] of fileMapRef.current.entries()) {
      if (entry.state.id === fileId) return uppyId;
    }
    return undefined;
  }, []);

  const updateFileState = useCallback((fileId: string, updates: Partial<UploadFileState>) => {
    setFiles((prev) => prev.map((f) => (f.id === fileId ? { ...f, ...updates } : f)));
  }, []);

  // Create Uppy instance with all event listeners registered immediately
  const getUppy = useCallback(() => {
    if (uppyRef.current) return uppyRef.current;

    const uppy = new Uppy({
      id: `uppy-${projectId}`,
      autoProceed: false,
      restrictions: {
        maxFileSize: UPLOAD_CONFIG.maxFileSize,
        allowedFileTypes: [...UPLOAD_CONFIG.allowedFileTypes],
      },
    });

    uppy.use(Tus, createTusOptions());

    uppy.on('file-added', (file) => {
      uppy.setFileMeta(file.id, {
        filename: file.name,
        filetype: file.type,
        project_id: projectId,
        role: fileRole,
      });
    });

    uppy.on('upload-progress', (file, progress) => {
      if (!file) return;
      const entry = fileMapRef.current.get(file.id);
      if (entry) {
        updateFileState(entry.state.id, {
          status: 'uploading',
          progress: createProgress(progress.bytesUploaded ?? 0, progress.bytesTotal ?? 1),
        });
      }
    });

    uppy.on('upload-success', (file) => {
      if (!file) return;
      const entry = fileMapRef.current.get(file.id);
      if (entry) {
        updateFileState(entry.state.id, {
          status: 'completed',
          progress: createProgress(file.size ?? 0, file.size ?? 0),
        });
        callbackRefs.current.onFileComplete?.(entry.file, file);
        queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      }
    });

    uppy.on('upload-error', (file, error) => {
      if (!file) return;
      const entry = fileMapRef.current.get(file.id);
      if (entry) {
        const errorMessage = error?.message || 'Upload failed';
        updateFileState(entry.state.id, { status: 'error', error: errorMessage });
        callbackRefs.current.onError?.(error ?? new Error(errorMessage), file.name ?? 'unknown');
        toast.error(`Failed to upload ${file.name}: ${errorMessage}`);
      }
    });

    uppy.on('complete', (result) => {
      if (result.successful && result.successful.length > 0) {
        callbackRefs.current.onAllComplete?.();
      }
    });

    uppy.on('pause-all', () => {
      setFiles((prev) => prev.map((f) => (f.status === 'uploading' ? { ...f, status: 'paused' as UploadStatus } : f)));
    });

    uppy.on('resume-all', () => {
      setFiles((prev) => prev.map((f) => (f.status === 'paused' ? { ...f, status: 'uploading' as UploadStatus } : f)));
    });

    uppyRef.current = uppy;
    return uppy;
  }, [projectId, fileRole, queryClient, updateFileState]);

  const addFiles = useCallback(
    (newFiles: File[]) => {
      const uppy = getUppy();
      const newStates: UploadFileState[] = [];

      for (const file of newFiles) {
        const stateId = `${projectId}-${file.name}-${Date.now()}-${Math.random()}`;
        const state: UploadFileState = {
          id: stateId,
          file,
          status: 'pending',
          progress: createProgress(0, file.size),
        };
        newStates.push(state);

        try {
          const uppyFileId = uppy.addFile({
            name: file.name,
            type: file.type,
            data: file,
            meta: { filename: file.name, filetype: file.type, project_id: projectId, role: fileRole },
          });
          fileMapRef.current.set(uppyFileId, { file, state });
        } catch (err) {
          state.status = 'error';
          state.error = err instanceof Error ? err.message : 'Failed to add file';
        }
      }

      setFiles((prev) => [...prev, ...newStates]);
    },
    [getUppy, projectId, fileRole],
  );

  const removeFile = useCallback(
    (fileId: string) => {
      const uppy = getUppy();
      const uppyId = findUppyId(fileId);
      if (uppyId) {
        try {
          uppy.removeFile(uppyId);
        } catch {
          // File might already be removed
        }
        fileMapRef.current.delete(uppyId);
      }
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
    },
    [getUppy, findUppyId],
  );

  const startUpload = useCallback(
    (filesToUpload?: File[]) => {
      const uppy = getUppy();
      if (filesToUpload && filesToUpload.length > 0) {
        addFiles(filesToUpload);
      }
      setFiles((prev) => prev.map((f) => (f.status === 'pending' ? { ...f, status: 'uploading' as UploadStatus } : f)));
      uppy.upload();
    },
    [getUppy, addFiles],
  );

  const pauseFile = useCallback(
    (fileId: string) => {
      const uppy = getUppy();
      const uppyId = findUppyId(fileId);
      if (uppyId) {
        uppy.pauseResume(uppyId);
        updateFileState(fileId, { status: 'paused' });
      }
    },
    [getUppy, findUppyId, updateFileState],
  );

  const resumeFile = useCallback(
    (fileId: string) => {
      const uppy = getUppy();
      const uppyId = findUppyId(fileId);
      if (uppyId) {
        uppy.pauseResume(uppyId);
        updateFileState(fileId, { status: 'uploading' });
      }
    },
    [getUppy, findUppyId, updateFileState],
  );

  const pauseAll = useCallback(() => getUppy().pauseAll(), [getUppy]);
  const resumeAll = useCallback(() => getUppy().resumeAll(), [getUppy]);

  const cancelAll = useCallback(() => {
    getUppy().cancelAll();
    setFiles((prev) =>
      prev.map((f) =>
        isActiveStatus(f.status) || f.status === 'paused'
          ? { ...f, status: 'error' as UploadStatus, error: 'Cancelled' }
          : f,
      ),
    );
  }, [getUppy]);

  const reset = useCallback(() => {
    if (uppyRef.current) {
      uppyRef.current.cancelAll();
      uppyRef.current.destroy();
      uppyRef.current = null;
    }
    fileMapRef.current.clear();
    setFiles([]);
  }, []);

  const isUploading = useMemo(() => files.some((f) => isActiveStatus(f.status)), [files]);
  const completedCount = useMemo(() => files.filter((f) => f.status === 'completed').length, [files]);
  const overallProgress = useMemo(
    () =>
      files.length > 0 ? Math.round(files.reduce((sum, f) => sum + f.progress.progress_percent, 0) / files.length) : 0,
    [files],
  );

  return {
    files,
    isUploading,
    overallProgress,
    completedCount,
    totalCount: files.length,
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
