export const TABS = ['document-explorer', 'summary', 'files', 'references', 'analyses'] as const;

export type TabType = (typeof TABS)[number];
