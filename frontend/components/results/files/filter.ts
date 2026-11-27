import { FileListItem, FileRole } from '@/lib/generated-api';
import { FileGroup, fileGroup } from './role';

/** What the rail narrows the table to: every file, or one kind. */
export type Lens = 'all' | FileGroup;

/**
 * The files the tab lists. Supporting candidates are a staging role the
 * reference downloader uses while it works, not files the project holds. The
 * API already leaves them out of overview.files (get_project_files_list_items
 * filters the role in SQL), so this is belt and braces, and the tab's counts
 * match the badge in the header because both read this same list.
 */
export function listedFiles(files: FileListItem[]): FileListItem[] {
  return files.filter((file) => file.role !== FileRole.SupportingCandidate);
}

/** How many files each lens shows, for the rail and the "N of M" line. */
export function countByLens(files: FileListItem[]): Record<Lens, number> {
  const counts: Record<Lens, number> = { all: files.length, main: 0, source: 0, memo: 0, response: 0, review: 0 };
  for (const file of files) counts[fileGroup(file.role)] += 1;
  return counts;
}

/** Whether the table hides any file: a kind is picked, or there is a search. */
export function isFiltered(lens: Lens, search: string): boolean {
  return lens !== 'all' || search.trim() !== '';
}

/**
 * The rows the table shows, in the order given: files of the lens's kind whose
 * name, description or matched reference contains the search, ignoring case
 * and surrounding spaces.
 */
export function filterFiles(
  files: FileListItem[],
  lens: Lens,
  search: string,
  referenceByFileId: ReadonlyMap<string, { text: string }>,
): FileListItem[] {
  const query = search.trim().toLowerCase();
  return files.filter((file) => {
    if (lens !== 'all' && fileGroup(file.role) !== lens) return false;
    if (!query) return true;
    return (
      !!file.file_name?.toLowerCase().includes(query) ||
      !!file.description?.toLowerCase().includes(query) ||
      !!referenceByFileId.get(file.id)?.text?.toLowerCase().includes(query)
    );
  });
}
