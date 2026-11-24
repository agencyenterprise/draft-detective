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

/** A file the API sent back, read with the SDK's `responseStyle: 'fields'` so its headers come too. */
export interface FileResponse {
  data: unknown;
  response: Response;
}

/**
 * Saves a file the API sent back under the name its `Content-Disposition` gives, else `fallbackFilename`.
 * The backend names exports after the uploaded document, which is what people track the file by.
 */
export function saveFileResponse({ data, response }: FileResponse, fallbackFilename: string): void {
  if (!(data instanceof Blob)) {
    throw new Error('Unexpected response type from file download');
  }
  const filename = filenameFromContentDisposition(response.headers.get('content-disposition')) ?? fallbackFilename;
  downloadFile({ blob: data, filename });
}

/**
 * The filename a `Content-Disposition` header names, or null when it names none.
 * Prefers the RFC 5987 `filename*` form, which is how servers send non-ASCII names.
 */
export function filenameFromContentDisposition(header: string | null): string | null {
  if (!header) return null;
  const encoded = /filename\*\s*=\s*([^']*)'[^']*'([^;]+)/i.exec(header);
  if (encoded) {
    try {
      return decodeURIComponent(encoded[2].trim());
    } catch {
      // Malformed percent-encoding: fall through to the plain form.
    }
  }
  const plain = /filename\s*=\s*(?:"([^"]*)"|([^;]+))/i.exec(header);
  const name = (plain?.[1] ?? plain?.[2])?.trim();
  return name || null;
}
