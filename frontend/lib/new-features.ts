const DEFAULT_VISIBLE_DAYS = 30;
const DAY_MS = 24 * 60 * 60 * 1000;

export interface NewFeatureRelease {
  /** The day the feature reached users, as YYYY-MM-DD (UTC). */
  releasedAt: string;
  /** How many days after the release the "New" badge stays up. Defaults to 30. */
  visibleDays?: number;
}

/**
 * Features recently released to everyone, which the UI marks "New", keyed by a
 * namespaced id: `workflow:<WorkflowRunType>` for assessments, and a namespace
 * of its own for anything else (`page:...`, `action:...`). An entry stops
 * showing on its own once its window passes, so stale ones are harmless, but
 * delete them when you next pass by.
 */
export const NEW_FEATURES: Record<string, NewFeatureRelease> = {
  'workflow:citation_consistency': { releasedAt: '2026-10-29' },
};

/** Whether the release is inside its badge window at `now`. */
export function isNewRelease(release: NewFeatureRelease | undefined, now: Date = new Date()): boolean {
  if (!release) return false;
  const releasedAt = new Date(`${release.releasedAt}T00:00:00Z`).getTime();
  const visibleDays = release.visibleDays ?? DEFAULT_VISIBLE_DAYS;
  const elapsed = now.getTime() - releasedAt;
  return elapsed >= 0 && elapsed < visibleDays * DAY_MS;
}

/** Whether the UI should mark the feature `id` "New" at `now`. */
export function isNewFeature(id: string, now: Date = new Date()): boolean {
  return isNewRelease(NEW_FEATURES[id], now);
}
