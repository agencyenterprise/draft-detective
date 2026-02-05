/**
 * Low-level Tus protocol client for chunked uploads.
 *
 * Implements the core Tus operations: create session, upload chunk, get offset, complete.
 * Uses raw fetch because the SDK can't handle binary body and response headers properly.
 */

import { baseUrl } from '../../api';
import { FileRole, File as FileRecord, UploadSessionResponse } from '../../generated-api';
import { TUS_VERSION, CHUNK_SIZE, MAX_RETRIES, RETRY_DELAYS } from './types';

// Header helpers
export function tusHeaders(authHeader: string, extra: Record<string, string> = {}): Record<string, string> {
  return { Authorization: authHeader, 'Tus-Resumable': TUS_VERSION, ...extra };
}

async function extractError(response: Response, context: string): Promise<never> {
  const error = await response.text();
  throw new Error(`${context}: ${error}`);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Create a new upload session (Tus POST).
 */
export async function createUploadSession(
  file: File,
  projectId: string,
  authHeader: string,
): Promise<UploadSessionResponse> {
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

/**
 * Get current upload offset (Tus HEAD).
 */
export async function getUploadOffset(sessionId: string, authHeader: string): Promise<number> {
  const response = await fetch(`${baseUrl}/api/upload/${sessionId}`, {
    method: 'HEAD',
    headers: tusHeaders(authHeader),
  });

  if (!response.ok) {
    throw new Error('Failed to get upload offset');
  }

  return parseInt(response.headers.get('Upload-Offset') || '0', 10);
}

/**
 * Complete an upload session and create the file record (POST).
 */
export async function completeUpload(sessionId: string, role: FileRole, authHeader: string): Promise<FileRecord> {
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
 * Upload a single chunk with automatic retry (Tus PATCH).
 */
export async function uploadChunk(
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
