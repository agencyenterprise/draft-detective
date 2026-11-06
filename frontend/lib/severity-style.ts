import { SeverityEnum } from './generated-api';

export interface SeverityStyle {
  /** Severity marker: the dot beside an issue, and the leader of an open margin note. */
  dot: string;
  /** Underline colour for a paragraph marked as a whole, in the dot's colour. */
  decoration: string;
  /** Border of an open note. */
  edge: string;
  /** Fill for the selected block and the open note. */
  wash: string;
  label: string;
  text: string;
}

/**
 * The one severity palette. The document, the margin, the issue list and the
 * reference-review explainer all read from here so a colour cannot drift
 * between where an issue is marked and where it is read.
 */
export const SEVERITY: Record<SeverityEnum, SeverityStyle> = {
  [SeverityEnum.High]: {
    dot: 'bg-red-500',
    decoration: 'decoration-red-500',
    edge: 'border-red-400 dark:border-red-700',
    wash: 'bg-red-50 dark:bg-red-950/30',
    label: 'High',
    text: 'text-red-700 dark:text-red-300',
  },
  [SeverityEnum.Medium]: {
    dot: 'bg-amber-500',
    decoration: 'decoration-amber-500',
    edge: 'border-amber-400 dark:border-amber-700',
    wash: 'bg-amber-50 dark:bg-amber-950/30',
    label: 'Medium',
    text: 'text-amber-800 dark:text-amber-300',
  },
  [SeverityEnum.Low]: {
    dot: 'bg-blue-500',
    decoration: 'decoration-blue-500',
    edge: 'border-blue-400 dark:border-blue-700',
    wash: 'bg-blue-50 dark:bg-blue-950/30',
    label: 'Low',
    text: 'text-blue-700 dark:text-blue-300',
  },
  [SeverityEnum.None]: {
    dot: 'bg-green-500',
    decoration: 'decoration-green-500',
    edge: 'border-green-400 dark:border-green-700',
    wash: 'bg-green-50 dark:bg-green-950/30',
    label: 'Passing',
    text: 'text-green-700 dark:text-green-300',
  },
};

/**
 * The style an issue is shown with. With grouping off every reported issue
 * takes the medium colours and no label, so none of them reads as optional;
 * passing checks stay green, since "passing" is not a priority.
 */
export function severityStyle(severity: SeverityEnum, groupBySeverity: boolean): SeverityStyle {
  if (groupBySeverity || severity === SeverityEnum.None) return SEVERITY[severity];
  return { ...SEVERITY[SeverityEnum.Medium], label: '' };
}
