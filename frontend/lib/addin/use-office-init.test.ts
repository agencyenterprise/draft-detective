import { afterEach, describe, expect, it, vi } from 'vitest';
import { officeReady } from './use-office-init';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('officeReady', () => {
  it('waits for office.js to arrive, then reports the host', async () => {
    vi.useFakeTimers();
    const ready = officeReady();

    vi.stubGlobal('Office', {
      onReady: () => Promise.resolve({ host: 'Word' }),
      HostType: { Word: 'Word' },
    });
    await vi.advanceTimersByTimeAsync(200);

    await expect(ready).resolves.toBe('Word');
  });

  it('gives up when office.js never loads, rather than hanging the pane', async () => {
    vi.useFakeTimers();
    const ready = officeReady();
    const outcome = expect(ready).rejects.toThrow('Office did not load');

    await vi.advanceTimersByTimeAsync(50 * 200);

    await outcome;
  });
});
