/**
 * Chunked upload service for resumable file uploads.
 *
 * Uses our backend's Tus-like API for reliable uploads with:
 * - Chunked transfer (5MB chunks)
 * - Automatic retry with exponential backoff
 * - Resume capability
 * - Progress tracking
 *
 * Note: Tus protocol endpoints (uploadChunk, createSession, getOffset) use raw fetch
 * because the SDK can't handle binary body and response headers properly.
 * Only completeUpload uses the generated SDK (standard JSON POST).
 */

import { getAuthHeader, baseUrl } from '../api';
import { FileRole, File as FileRecord, UploadSessionResponse, UploadStatusResponse } from '../generated-api';

// Constants
const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB chunks
const MAX_RETRIES = 3;
const RETRY_DELAYS = [1000, 3000, 5000];
const TUS_VERSION = '1.0.0';

// Upload status type and helpers (used by use-upload.ts and upload-progress-list.tsx)
export type UploadStatus = 'pending' | 'uploading' | 'paused' | 'completing' | 'completed' | 'error';

export const ACTIVE_STATUSES = new Set<UploadStatus>(['pending', 'uploading', 'completing']);

export function isActiveStatus(status: UploadStatus): boolean {
  return ACTIVE_STATUSES.has(status);
}

// Types derived from API
export type UploadProgress = Pick<UploadStatusResponse, 'uploaded_size' | 'total_size' | 'progress_percent'>;

// Client-side callback interface (no API equivalent)
export interface UploadCallbacks {
  onProgress?: (progress: UploadProgress) => void;
  onSuccess?: (fileRecord: FileRecord) => void;
  onError?: (error: Error) => void;
}

// Input params for uploadFile function (transformed to API request internally)
export interface UploadMetadata {
  projectId: string;
  filename: string;
  fileRole?: FileRole;
}

// Client-side state machine combining API responses with browser APIs
export interface ChunkedUploadState {
  id: string;
  sessionId: UploadSessionResponse['session_id'] | null;
  file: File; // Browser File API
  status: UploadStatus;
  progress: UploadProgress;
  error?: string;
  fileRecord?: FileRecord;
  abortController: AbortController | null; // Browser AbortController API
}

// Helpers
function tusHeaders(authHeader: string, extra: Record<string, string> = {}): Record<string, string> {
  return { Authorization: authHeader, 'Tus-Resumable': TUS_VERSION, ...extra };
}

async function extractError(response: Response, context: string): Promise<never> {
  const error = await response.text();
  throw new Error(`${context}: ${error}`);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function createProgress(uploaded_size: number, total_size: number): UploadProgress {
  return {
    uploaded_size,
    total_size,
    progress_percent: total_size > 0 ? Math.round((uploaded_size / total_size) * 100) : 0,
  };
}

// Tus API functions (must use raw fetch - SDK can't handle binary body/headers)
async function createUploadSession(file: File, projectId: string, authHeader: string): Promise<UploadSessionResponse> {
  const filenameBase64 = btoa(unescape(encodeURIComponent(file.name)));

  const response = await fetch(`${baseUrl}/api/upload?project_id=${projectId}`, {
    method: 'POST',
    headers: tusHeaders(authHeader, {
      'Upload-Length': String(file.size),
      'Upload-Metadata': `filename ${filenameBase64}`,
    }),
  });

  if (!response.ok) {
    await extractError(response, 'Failed to create upload session');
  }

  return response.json();
}

async function getUploadOffset(sessionId: string, authHeader: string): Promise<number> {
  const response = await fetch(`${baseUrl}/api/upload/${sessionId}`, {
    method: 'HEAD',
    headers: tusHeaders(authHeader),
  });

  if (!response.ok) {
    throw new Error('Failed to get upload offset');
  }

  return parseInt(response.headers.get('Upload-Offset') || '0', 10);
}

async function completeUpload(sessionId: string, role: FileRole, authHeader: string): Promise<FileRecord> {
  const response = await fetch(`${baseUrl}/api/upload/${sessionId}/complete?role=${role}`, {
    method: 'POST',
    headers: { Authorization: authHeader },
  });

  if (!response.ok) {
    await extractError(response, 'Failed to complete upload');
  }

  return response.json();
}

/**
 * Upload a single chunk with automatic retry.
 */
async function uploadChunk(
  sessionId: string,
  file: File,
  initialOffset: number,
  authHeader: string,
  signal: AbortSignal,
): Promise<number> {
  let offset = initialOffset;
  let retries = 0;

  while (retries <= MAX_RETRIES) {
    const chunk = file.slice(offset, offset + CHUNK_SIZE);

    try {
      const response = await fetch(`${baseUrl}/api/upload/${sessionId}`, {
        method: 'PATCH',
        headers: tusHeaders(authHeader, {
          'Content-Type': 'application/offset+octet-stream',
          'Upload-Offset': String(offset),
        }),
        body: chunk,
        signal,
      });

      if (!response.ok) {
        await extractError(response, 'Failed to upload chunk');
      }

      const newOffsetHeader = response.headers.get('Upload-Offset');
      if (!newOffsetHeader) {
        console.warn('Upload-Offset header missing from response, calculating manually');
        return offset + chunk.size;
      }

      return parseInt(newOffsetHeader, 10);
    } catch (error) {
      if (signal.aborted) throw error;

      retries++;
      if (retries > MAX_RETRIES) throw error;

      await sleep(RETRY_DELAYS[retries - 1] || 5000);

      // Sync offset with server in case of partial upload
      try {
        offset = await getUploadOffset(sessionId, authHeader);
      } catch {
        // Keep current offset if HEAD request fails
      }
    }
  }

  throw new Error('Upload failed after retries');
}

/**
 * Upload a file with chunking and automatic retry.
 */
export async function uploadFile(
  file: File,
  metadata: UploadMetadata,
  callbacks: UploadCallbacks = {},
): Promise<ChunkedUploadState> {
  const authHeader = await getAuthHeader();
  if (!authHeader) {
    throw new Error('Authentication required for upload');
  }

  const state: ChunkedUploadState = {
    id: `${metadata.projectId}-${file.name}-${Date.now()}`,
    sessionId: null,
    file,
    status: 'pending',
    progress: createProgress(0, file.size),
    error: undefined,
    abortController: new AbortController(),
  };

  const updateProgress = (uploaded_size: number) => {
    state.progress = createProgress(uploaded_size, file.size);
    callbacks.onProgress?.(state.progress);
  };

  const isAborted = () => state.abortController?.signal.aborted ?? false;

  try {
    // Step 1: Create upload session
    state.status = 'uploading';
    const { session_id: sessionId } = await createUploadSession(file, metadata.projectId, authHeader);
    state.sessionId = sessionId;

    // Step 2: Upload chunks with retry
    let offset = 0;
    while (offset < file.size) {
      if (isAborted()) throw new Error('Upload cancelled');

      offset = await uploadChunk(sessionId, file, offset, authHeader, state.abortController!.signal);
      updateProgress(offset);
    }

    // Step 3: Complete upload
    state.status = 'completing';
    const fileRecord = await completeUpload(sessionId, metadata.fileRole || FileRole.Support, authHeader);

    state.status = 'completed';
    state.fileRecord = fileRecord;
    state.progress.progress_percent = 100;
    callbacks.onSuccess?.(fileRecord);

    return state;
  } catch (error) {
    state.status = 'error';
    state.error = error instanceof Error ? error.message : 'Upload failed';
    callbacks.onError?.(error instanceof Error ? error : new Error('Upload failed'));
    return state;
  }
}

/**
 * Cancel an upload.
 */
export function cancelUpload(state: ChunkedUploadState): void {
  if (state.abortController) {
    state.abortController.abort();
    state.status = 'error';
    state.error = 'Upload cancelled';
  }
}

/**
 * Formats bytes to human-readable string.
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}
