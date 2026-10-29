import { describe, expect, it } from 'vitest';
import { isNewFeature, isNewRelease } from './new-features';

describe('isNewRelease', () => {
  const release = { releasedAt: '2026-10-29' };

  it('is new from the release day through the 30-day default window', () => {
    expect(isNewRelease(release, new Date('2026-10-29T00:00:00Z'))).toBe(true);
    expect(isNewRelease(release, new Date('2026-11-27T23:59:59Z'))).toBe(true);
    expect(isNewRelease(release, new Date('2026-11-28T00:00:00Z'))).toBe(false);
  });

  it('is not new before the release day', () => {
    expect(isNewRelease(release, new Date('2026-10-28T23:59:59Z'))).toBe(false);
  });

  it('honours a custom window', () => {
    const short = { releasedAt: '2026-10-29', visibleDays: 7 };
    expect(isNewRelease(short, new Date('2026-11-04T12:00:00Z'))).toBe(true);
    expect(isNewRelease(short, new Date('2026-11-05T00:00:00Z'))).toBe(false);
  });

  it('is not new without a release entry', () => {
    expect(isNewRelease(undefined)).toBe(false);
  });
});

describe('isNewFeature', () => {
  it('looks the feature up in the registry', () => {
    const now = new Date('2026-11-01T00:00:00Z');
    expect(isNewFeature('workflow:citation_consistency', now)).toBe(true);
    expect(isNewFeature('workflow:active_voice', now)).toBe(false);
  });
});
