/**
 * High-level chunked upload orchestration.
 *
 * Provides uploadFile, pauseUpload, resumeUpload, and cancelUpload functions
 * that coordinate the Tus protocol operations.
 */

import { getAuthHeader } from '../../api';
import { FileRole } from '../../generated-api';
import { ChunkedUploadState, UploadCallbacks, UploadMetadata, createProgress } from './types';
import { createUploadSession, getUploadOffset, uploadChunk, completeUpload } from './tus-client';

/**
 * Upload a file with chunking, retry, and pause/resume support.
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
    isPaused: false,
    metadata,
  };

  const updateProgress = (uploaded_size: number) => {
    state.progress = createProgress(uploaded_size, file.size);
    callbacks.onProgress?.(state.progress);
  };

  try {
    state.status = 'uploading';
    const { session_id: sessionId } = await createUploadSession(file, metadata.projectId, authHeader);
    state.sessionId = sessionId;

    let offset = 0;
    while (offset < file.size) {
      if (state.abortController?.signal.aborted) throw new Error('Upload cancelled');
      if (state.isPaused) {
        state.status = 'paused';
        return state;
      }

      offset = await uploadChunk(sessionId, file, offset, authHeader, state.abortController!.signal);
      updateProgress(offset);
    }

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
 * Cancel an upload by aborting the request.
 */
export function cancelUpload(state: ChunkedUploadState): void {
  if (state.abortController) {
    state.abortController.abort();
    state.status = 'error';
    state.error = 'Upload cancelled';
  }
}

/**
 * Pause an upload. Completes the current chunk before pausing.
 */
export function pauseUpload(state: ChunkedUploadState): void {
  if (state.status === 'uploading') {
    state.isPaused = true;
  }
}

/**
 * Resume a paused upload from where it left off.
 */
export async function resumeUpload(
  state: ChunkedUploadState,
  callbacks: UploadCallbacks = {},
): Promise<ChunkedUploadState> {
  if (state.status !== 'paused' || !state.sessionId) {
    return state;
  }

  const authHeader = await getAuthHeader();
  if (!authHeader) {
    state.status = 'error';
    state.error = 'Authentication required';
    return state;
  }

  state.isPaused = false;
  state.abortController = new AbortController();
  state.status = 'uploading';

  const updateProgress = (uploaded_size: number) => {
    state.progress = createProgress(uploaded_size, state.file.size);
    callbacks.onProgress?.(state.progress);
  };

  try {
    let offset = await getUploadOffset(state.sessionId, authHeader);
    updateProgress(offset);

    while (offset < state.file.size) {
      if (state.abortController?.signal.aborted) throw new Error('Upload cancelled');
      if (state.isPaused) {
        state.status = 'paused';
        return state;
      }

      offset = await uploadChunk(state.sessionId, state.file, offset, authHeader, state.abortController!.signal);
      updateProgress(offset);
    }

    state.status = 'completing';
    const fileRecord = await completeUpload(state.sessionId, state.metadata.fileRole || FileRole.Support, authHeader);

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
