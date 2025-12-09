/**
 * Service for managing share links.
 */

import { apiUrl, getAuthHeader } from '@/lib/api';

export interface ShareLinkResponse {
  token: string;
  url: string;
  is_active: boolean;
}

export interface ShareStatusResponse {
  enabled: boolean;
  share_link: ShareLinkResponse | null;
}

async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const authHeader = await getAuthHeader();
  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      ...(authHeader ? { Authorization: authHeader } : {}),
    },
  });
}

export async function getShareStatus(projectId: string): Promise<ShareStatusResponse> {
  const response = await fetchWithAuth(`${apiUrl}/api/projects/${projectId}/share`);
  if (!response.ok) {
    throw new Error('Failed to get share status');
  }
  return response.json();
}

export async function enableSharing(projectId: string): Promise<ShareStatusResponse> {
  const response = await fetchWithAuth(`${apiUrl}/api/projects/${projectId}/share/enable`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error('Failed to enable sharing');
  }
  return response.json();
}

export async function disableSharing(projectId: string): Promise<ShareStatusResponse> {
  const response = await fetchWithAuth(`${apiUrl}/api/projects/${projectId}/share/disable`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error('Failed to disable sharing');
  }
  return response.json();
}
