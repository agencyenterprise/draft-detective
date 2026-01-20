export const TABS = ['document-explorer', 'summary', 'files', 'references', 'reference-review', 'analyses'] as const;

export type TabType = (typeof TABS)[number];
