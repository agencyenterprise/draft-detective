import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function generateDefaultTestName(prefix: string, suffix?: string): string {
  const timestamp = Date.now();
  return suffix ? `${prefix}_${suffix}_${timestamp}` : `${prefix}_${timestamp}`;
}

export async function downloadBlobResponse(apiCall: () => Promise<{ raw: Response }>): Promise<Blob> {
  const apiResponse = await apiCall();
  return await apiResponse.raw.blob();
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function snakeCaseToTitleCase(s: string): string {
  return s?.replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase()) || '';
}

/**
 * Format technical reference fetch error messages into user-friendly explanations.
 * Backend already transforms most errors, but this provides a fallback for edge cases.
 */
export function formatReferenceError(error: string | null | undefined): string {
  if (!error) return 'An unknown error occurred while fetching this reference.';

  // Check for recursion limit error (fallback in case backend doesn't catch it)
  if (error.toLowerCase().includes('recursion limit')) {
    return "We searched extensively but couldn't find an accessible version of this reference. The source may be behind a paywall or have restricted access.";
  }

  return error;
}
