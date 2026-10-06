import { FileListItem, FileRole } from '@/lib/generated-api';

/** The kinds of file a project holds, as the tab groups them. */
export type FileGroup = 'main' | 'source' | 'memo' | 'response';

export const GROUP: Record<FileGroup, { label: string; plural: string; description: string; className: string }> = {
  main: {
    label: 'Main document',
    plural: 'Main document',
    description: 'The draft under review. Every assessment reads this document, and it is what the explorer shows.',
    className: 'bg-primary/10 text-primary',
  },
  source: {
    label: 'Source',
    plural: 'Sources',
    description: 'A document one of your references cites. Assessments that check citations read it.',
    className: 'bg-secondary text-secondary-foreground',
  },
  memo: {
    label: 'Reviewer memo',
    plural: 'Reviewer memos',
    description: 'Peer-review feedback on a draft, read by the Peer Review assessments.',
    className: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200',
  },
  response: {
    label: 'Response memo',
    plural: 'Response memos',
    description:
      "The author's reply to a reviewer, attached to the revised draft it describes. The QA coverage report checks it against that draft.",
    className: 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200',
  },
};

/** Supporting candidates are filtered out before this, and read as sources if any slip through. */
export function fileGroup(role: FileRole): FileGroup {
  if (role === FileRole.Main) return 'main';
  if (role === FileRole.ReviewerMemo) return 'memo';
  if (role === FileRole.ResponseMemo) return 'response';
  return 'source';
}

/** The line under a role tag: which revision this file belongs to, and whether it still stands. */
export function revisionLabel(file: FileListItem, currentRevision: number): string | null {
  if (file.revision == null) return null;
  if (file.role !== FileRole.Main) return `Revision ${file.revision}`;
  return file.revision === currentRevision
    ? `Revision ${file.revision} · current`
    : `Revision ${file.revision} · superseded`;
}

const RANK: Partial<Record<FileRole, number>> = {
  [FileRole.Main]: 0,
  [FileRole.ReviewerMemo]: 1,
  [FileRole.ResponseMemo]: 2,
};

/** Main first (newest revision first), then reviewer and response memos, then sources by name. */
export function sortFiles(files: FileListItem[]): FileListItem[] {
  const rank = (role: FileRole) => RANK[role] ?? 3;
  return [...files].sort((a, b) => {
    const byRank = rank(a.role) - rank(b.role);
    if (byRank !== 0) return byRank;
    if (a.role === FileRole.Main && b.role === FileRole.Main) return (b.revision ?? 0) - (a.revision ?? 0);
    return (a.file_name || '').localeCompare(b.file_name || '');
  });
}
