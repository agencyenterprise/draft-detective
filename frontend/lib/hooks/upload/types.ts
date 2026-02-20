import type { Meta, UppyFile } from '@uppy/core';
import type { FileRole } from '../../generated-api';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyBody = any;

export type UploadStatus = 'pending' | 'uploading' | 'paused' | 'completing' | 'completed' | 'error';

export interface UploadProgress {
  uploaded_size: number;
  total_size: number;
  progress_percent: number;
}

export interface UploadFileState {
  id: string;
  file: File;
  status: UploadStatus;
  progress: UploadProgress;
  error?: string;
}

export interface UseUploadOptions {
  /** The project ID to upload the files to. */
  projectId: string;
  /** The role of the file to upload. */
  fileRole?: FileRole;
  /** When set, the backend will force-match the uploaded file to this reference. */
  referenceId?: string;
  /** Callback when a file is completed. */
  onFileComplete?: (file: File, uppyFile: UppyFile<Meta, AnyBody>) => void;
  /** Callback when all files are completed. */
  onAllComplete?: () => void;
  /** Callback when an error occurs. */
  onError?: (error: Error, fileName: string) => void;
}

export interface UseUploadReturn {
  files: UploadFileState[];
  isUploading: boolean;
  overallProgress: number;
  completedCount: number;
  totalCount: number;
  addFiles: (files: File[]) => void;
  removeFile: (fileId: string) => void;
  startUpload: (filesToUpload?: File[]) => void;
  pauseFile: (fileId: string) => void;
  resumeFile: (fileId: string) => void;
  pauseAll: () => void;
  resumeAll: () => void;
  cancelAll: () => void;
  reset: () => void;
}

export interface SingleUploadOptions {
  projectId: string;
  fileRole: FileRole;
  onProgress?: (progress: UploadProgress) => void;
}

export function createProgress(uploaded: number, total: number): UploadProgress {
  return {
    uploaded_size: uploaded,
    total_size: total,
    progress_percent: total > 0 ? Math.round((uploaded / total) * 100) : 0,
  };
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function isActiveStatus(status: UploadStatus): boolean {
  return status === 'pending' || status === 'uploading' || status === 'completing';
}
