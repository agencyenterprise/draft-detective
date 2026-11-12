export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail?: string,
  ) {
    super(detail ?? `HTTP ${status}`);
    this.name = 'ApiError';
  }
}

export function isApiError(error: unknown, status?: number): error is ApiError {
  return error instanceof ApiError && (status === undefined || error.status === status);
}

/**
 * Extract a user-readable message from an unknown error value.
 * An ApiError shows the server's reason, or the fallback when the server gave none
 * (never the bare "HTTP <status>"). Any other Error shows its own message.
 */
export function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.detail || fallback;
  if (error instanceof Error) return error.message;
  return fallback;
}
