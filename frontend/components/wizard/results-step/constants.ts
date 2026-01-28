export const TABS = ['document-explorer', 'summary', 'references', 'files', 'analyses'] as const;

export type TabType = (typeof TABS)[number];
