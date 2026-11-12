import { describe, expect, it } from 'vitest';
import { ApiError, getErrorMessage } from './api-error';

describe('getErrorMessage', () => {
  it('shows the server reason an API error carries', () => {
    expect(getErrorMessage(new ApiError(409, 'Project is busy'), 'Failed to start')).toBe('Project is busy');
  });

  it('shows the fallback for an API error without a reason, not "HTTP <status>"', () => {
    expect(getErrorMessage(new ApiError(502), 'Failed to start assessment')).toBe('Failed to start assessment');
  });

  it("keeps a non-API error's own message", () => {
    expect(getErrorMessage(new Error('Pick a file first'), 'Failed to upload')).toBe('Pick a file first');
  });

  it('shows the fallback for a value that is not an error', () => {
    expect(getErrorMessage('boom', 'Failed to save')).toBe('Failed to save');
  });
});
