/**
 * Single file upload using Uppy with TUS protocol.
 * Used by the wizard for main document upload.
 */

import Uppy from '@uppy/core';
import Tus from '@uppy/tus';
import { getAuthHeader } from '../../api';
import { UPLOAD_CONFIG, createTusOptions } from './config';
import { createProgress, type SingleUploadOptions } from './types';

export async function uploadSingleFile(file: File, options: SingleUploadOptions): Promise<void> {
  const { projectId, fileRole, onProgress } = options;
  const authHeader = await getAuthHeader();

  if (!authHeader) {
    throw new Error('Authentication required. Please sign in and try again.');
  }

  const uppy = new Uppy({
    id: `single-upload-${projectId}-${Date.now()}`,
    autoProceed: true,
    restrictions: {
      maxFileSize: UPLOAD_CONFIG.maxFileSize,
      maxNumberOfFiles: 1,
    },
  });

  uppy.use(Tus, createTusOptions());

  return new Promise((resolve, reject) => {
    uppy.on('upload-progress', (_, progress) => {
      onProgress?.(createProgress(progress.bytesUploaded ?? 0, progress.bytesTotal ?? 1));
    });

    uppy.on('upload-success', () => {
      uppy.destroy();
      resolve();
    });

    uppy.on('upload-error', (_, error) => {
      uppy.destroy();
      reject(error || new Error('Upload failed'));
    });

    uppy.addFile({
      name: file.name,
      type: file.type,
      data: file,
      meta: {
        filename: file.name,
        filetype: file.type,
        project_id: projectId,
        role: fileRole,
      },
    });
  });
}
