/**
 * Shared upload configuration and Tus options factory.
 */

import { getAuthHeader, baseUrl } from '../../api';

export const UPLOAD_CONFIG = {
  maxFileSize: 500 * 1024 * 1024,
  chunkSize: 5 * 1024 * 1024,
  retryDelays: [0, 1000, 3000, 5000],
  allowedFileTypes: ['.pdf', '.doc', '.docx', '.txt', '.md'],
} as const;

export function createTusOptions() {
  return {
    endpoint: `${baseUrl}/tus/`,
    chunkSize: UPLOAD_CONFIG.chunkSize,
    retryDelays: [...UPLOAD_CONFIG.retryDelays],
    onBeforeRequest: async (req: { setHeader: (key: string, value: string) => void }) => {
      const auth = await getAuthHeader();
      if (auth) req.setHeader('Authorization', auth);
    },
    removeFingerprintOnSuccess: true,
  };
}
