/**
 * Types, constants, and utilities for chunked file uploads.
 */

import { FileRole, File as FileRecord, UploadStatusResponse } from '../../generated-api';

// Constants
export const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB chunks
export const MAX_RETRIES = 3;
export const RETRY_DELAYS = [1000, 3000, 5000];
export const TUS_VERSION = '1.0.0';

// Upload status
export type UploadStatus = 'pending' | 'uploading' | 'paused' | 'completing' | 'completed' | 'error';

export const ACTIVE_STATUSES = new Set<UploadStatus>(['pending', 'uploading', 'completing']);

export function isActiveStatus(status: UploadStatus): boolean {
  return ACTIVE_STATUSES.has(status);
}

// Progress tracking
export type UploadProgress = Pick<UploadStatusResponse, 'uploaded_size' | 'total_size' | 'progress_percent'>;

export function createProgress(uploaded_size: number, total_size: number): UploadProgress {
  return {
    uploaded_size,
    total_size,
    progress_percent: total_size > 0 ? Math.round((uploaded_size / total_size) * 100) : 0,
  };
}

// Callbacks for upload lifecycle
export interface UploadCallbacks {
  onProgress?: (progress: UploadProgress) => void;
  onSuccess?: (fileRecord: FileRecord) => void;
  onError?: (error: Error) => void;
}

// Input metadata for starting an upload
export interface UploadMetadata {
  projectId: string;
  filename: string;
  fileRole?: FileRole;
}

// Client-side upload state machine
export interface ChunkedUploadState {
  id: string;
  sessionId: string | null;
  file: File;
  status: UploadStatus;
  progress: UploadProgress;
  error?: string;
  fileRecord?: FileRecord;
  abortController: AbortController | null;
  isPaused: boolean;
  metadata: UploadMetadata;
}

// Utility
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}
