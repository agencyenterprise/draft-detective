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
 * The server's own reason for rejecting a request (an ApiError's `detail`), or `fallback` when there is
 * none: a bare "HTTP <status>" or a network error's message means nothing to the user.
 */
export function getErrorDetail(error: unknown, fallback: string): string {
  return (isApiError(error) && error.detail) || fallback;
}

/**
 * Like `getErrorDetail`, except that an Error not from the API (a network failure, a client-side
 * throw) shows its own message rather than the fallback.
 */
export function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && !isApiError(error)) return error.message;
  return getErrorDetail(error, fallback);
}
