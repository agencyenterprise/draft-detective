/**
 * Utilities for file download operations.
 */

export interface DownloadOptions {
  filename: string;
  blob: Blob;
}

/**
 * Triggers a download of a blob file in the browser.
 */
export function downloadFile({ filename, blob }: DownloadOptions): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');

  link.href = url;
  link.download = filename;

  // Temporarily add to DOM and trigger click
  document.body.appendChild(link);
  link.click();

  // Clean up
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

/**
 * Downloads data as a JSON file.
 */
export function downloadAsJson(data: unknown, filename: string = 'results'): void {
  const jsonString = JSON.stringify(data, null, 2);
  const blob = new Blob([jsonString], { type: 'application/json' });
  downloadFile({ filename: `${filename}.json`, blob });
}
