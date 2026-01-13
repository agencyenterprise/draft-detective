/**
 * Format milliseconds into a human-readable duration string.
 * @param ms - Duration in milliseconds
 * @returns Formatted string like "2m 34s" or "45s"
 */
export function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;

  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`;
  }
  return `${seconds}s`;
}
