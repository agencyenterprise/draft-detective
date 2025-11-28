export const TABS = [
  'document-explorer',
  'summary',
  'files',
  'references',
  'literature_review',
  'live_reports',
  'methodological_alignment',
] as const;

export type TabType = (typeof TABS)[number];

export const TAB_LABELS: Record<TabType, string> = {
  summary: 'Summary',
  'document-explorer': 'Explorer',
  files: 'Files',
  references: 'References',
  literature_review: 'Literature Review',
  live_reports: 'Live Reports',
  methodological_alignment: 'Methodological Alignment',
};
