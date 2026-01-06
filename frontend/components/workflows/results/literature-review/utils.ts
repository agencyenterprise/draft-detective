import { QualityLevel, ReferenceDirection, PoliticalBias, ReferenceType } from '@/lib/generated-api';

/**
 * Convert snake_case to Title Case with spaces
 */
export function humanizeLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Format quality level for display
 */
export function formatQuality(quality: QualityLevel): { label: string; className: string } {
  switch (quality) {
    case QualityLevel.High:
      return { label: 'High Quality', className: 'text-green-700 bg-green-50 border-green-200' };
    case QualityLevel.Medium:
      return { label: 'Medium Quality', className: 'text-yellow-700 bg-yellow-50 border-yellow-200' };
    case QualityLevel.Low:
      return { label: 'Low Quality', className: 'text-orange-700 bg-orange-50 border-orange-200' };
  }
}

/**
 * Format reference direction for display
 */
export function formatReferenceDirection(direction: ReferenceDirection): {
  label: string;
  className: string;
  icon: string;
} {
  switch (direction) {
    case ReferenceDirection.Supporting:
      return { label: 'Supporting', className: 'text-blue-700 bg-blue-50 border-blue-200', icon: '✓' };
    case ReferenceDirection.Conflicting:
      return { label: 'Conflicting', className: 'text-red-700 bg-red-50 border-red-200', icon: '✗' };
    case ReferenceDirection.Mixed:
      return { label: 'Mixed', className: 'text-purple-700 bg-purple-50 border-purple-200', icon: '~' };
    case ReferenceDirection.Contextual:
      return { label: 'Contextual', className: 'text-gray-700 bg-gray-50 border-gray-200', icon: 'ℹ' };
  }
}

/**
 * Format reference type for display
 */
export function formatReferenceType(type: ReferenceType): string {
  const typeMap: Record<ReferenceType, string> = {
    [ReferenceType.PeerReviewedPublication]: 'Peer-Reviewed Publication',
    [ReferenceType.Preprint]: 'Preprint',
    [ReferenceType.Book]: 'Book',
    [ReferenceType.GovernmentNgoReport]: 'Government/NGO Report',
    [ReferenceType.DataSoftware]: 'Data/Software',
    [ReferenceType.NewsMedia]: 'News Media',
    [ReferenceType.Reference]: 'Reference Work',
    [ReferenceType.Webpage]: 'Web Page',
  };
  return typeMap[type] || type;
}

/**
 * Format recommended action for display
 */
export function formatRecommendedAction(action: string): {
  label: string;
  className: string;
} {
  const actionMap: Record<string, { label: string; className: string }> = {
    add_new_citation: {
      label: 'Add New Citation',
      className: 'text-green-700 bg-green-50 border-green-200',
    },
    cite_existing_reference_in_new_place: {
      label: 'Cite Existing Reference',
      className: 'text-blue-700 bg-blue-50 border-blue-200',
    },
    replace_existing_reference: {
      label: 'Replace Reference',
      className: 'text-orange-700 bg-orange-50 border-orange-200',
    },
    discuss_reference: {
      label: 'Discuss Reference',
      className: 'text-purple-700 bg-purple-50 border-purple-200',
    },
    no_action: {
      label: 'No Action',
      className: 'text-gray-700 bg-gray-50 border-gray-200',
    },
    other: {
      label: 'Other',
      className: 'text-gray-700 bg-gray-50 border-gray-200',
    },
  };
  return actionMap[action] || { label: action, className: 'text-gray-700 bg-gray-50 border-gray-200' };
}

/**
 * Create filter options from enum values with humanized labels
 */
export function createFilterOptions<T extends string>(
  enumObject: Record<string, T>,
): Array<{ value: T | 'all'; label: string }> {
  return [
    { value: 'all' as const, label: 'All' },
    ...Object.values(enumObject).map((v) => ({
      value: v,
      label: humanizeLabel(v),
    })),
  ];
}

/**
 * Format political bias for display
 */
export function formatPoliticalBias(bias: PoliticalBias): string {
  const biasMap: Record<PoliticalBias, string> = {
    [PoliticalBias.Conservative]: 'Conservative',
    [PoliticalBias.Liberal]: 'Liberal',
    [PoliticalBias.Other]: 'Neutral/Other',
  };
  return biasMap[bias] || bias;
}
