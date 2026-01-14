/**
 * Feature flags controlled by environment variables.
 * These allow toggling features between environments (dev vs prod).
 */
export const featureFlags = {
  /**
   * When true, shows experimental workflow analyses in the UI.
   * Set NEXT_PUBLIC_SHOW_EXPERIMENTAL_FEATURES=true in .env to enable.
   */
  showExperimentalFeatures: process.env.NEXT_PUBLIC_SHOW_EXPERIMENTAL_FEATURES === 'true',
} as const;
