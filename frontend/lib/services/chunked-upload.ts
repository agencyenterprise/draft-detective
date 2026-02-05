/**
 * Chunked upload service for resumable file uploads.
 *
 * This is a re-export barrel for backward compatibility.
 * The actual implementation is in ./upload/
 *
 * @see ./upload/types.ts - Types, constants, utilities
 * @see ./upload/tus-client.ts - Low-level Tus protocol
 * @see ./upload/chunked-upload.ts - High-level orchestration
 */

export {
  // Types
  type UploadStatus,
  type UploadProgress,
  type UploadCallbacks,
  type UploadMetadata,
  type ChunkedUploadState,
  // Constants & utilities
  ACTIVE_STATUSES,
  isActiveStatus,
  createProgress,
  formatBytes,
  // Upload operations
  uploadFile,
  cancelUpload,
  pauseUpload,
  resumeUpload,
} from './upload';
