import { describe, expect, it } from 'vitest';
import { ApiError, getErrorDetail } from './api-error';

describe('getErrorDetail', () => {
  it("returns the server's reason", () => {
    expect(getErrorDetail(new ApiError(422, 'Incorrect API key provided'), 'fallback')).toBe(
      'Incorrect API key provided',
    );
  });

  it.each([
    ['an API error with no reason', new ApiError(502)],
    ['an API error with a blank reason', new ApiError(422, '')],
    ['a network failure', new TypeError('Failed to fetch')],
    ['a non-error value', 'boom'],
  ])('falls back on %s', (_case, error) => {
    expect(getErrorDetail(error, 'fallback')).toBe('fallback');
  });
});
