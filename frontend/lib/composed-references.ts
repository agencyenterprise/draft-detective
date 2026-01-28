/**
 * Utility for composing reference data from split workflow states.
 *
 * The backend splits reference processing into two workflows:
 * - ReferenceExtraction: extracts references (id, text)
 * - ReferenceFileMatching: matches references to supporting files (reference_id, file_id)
 *
 * This module provides utilities to compose them into a unified view.
 */

import { ExtractedReference, FileListItem, ReferenceFileMatch } from './generated-api';

/**
 * A composed reference combining extraction and file matching data.
 * This matches the old BibliographyItem interface for backward compatibility.
 */
export interface ComposedReference {
  id: string;
  text: string;
  has_associated_supporting_document: boolean;
  file_id: string | null;
  name_of_associated_supporting_document: string | null;
  index_of_associated_supporting_document: number;
}

/**
 * Compose references from extraction state and file matching state.
 *
 * @param extractedRefs - References extracted from the document
 * @param matches - File matches from the matching workflow (optional)
 * @param files - Project files to get file names (optional)
 * @returns Array of composed references with file matching info
 */
export function composeReferences(
  extractedRefs: ExtractedReference[] | undefined,
  matches: ReferenceFileMatch[] | undefined,
  files: FileListItem[] | undefined,
): ComposedReference[] {
  if (!extractedRefs || extractedRefs.length === 0) {
    return [];
  }

  // Build lookup maps for efficient matching
  const matchByRefId = new Map<string, ReferenceFileMatch>();
  if (matches) {
    for (const match of matches) {
      matchByRefId.set(match.reference_id, match);
    }
  }

  const fileById = new Map<string, FileListItem>();
  const fileIndexById = new Map<string, number>();
  if (files) {
    files.forEach((file, index) => {
      if (file.id) {
        fileById.set(file.id, file);
        fileIndexById.set(file.id, index + 1); // 1-based index
      }
    });
  }

  return extractedRefs.map((ref): ComposedReference => {
    const refId = ref.id ?? '';
    const match = matchByRefId.get(refId);
    const fileId = match?.file_id ?? null;
    const file = fileId ? fileById.get(fileId) : undefined;

    return {
      id: refId,
      text: ref.text,
      has_associated_supporting_document: !!fileId,
      file_id: fileId,
      name_of_associated_supporting_document: file?.file_name ?? null,
      index_of_associated_supporting_document: fileId ? (fileIndexById.get(fileId) ?? -1) : -1,
    };
  });
}

/**
 * Build a map of file_id to composed reference for quick lookups.
 */
export function buildReferenceByFileIdMap(references: ComposedReference[]): Map<string, ComposedReference> {
  const map = new Map<string, ComposedReference>();
  for (const ref of references) {
    if (ref.file_id) {
      map.set(ref.file_id, ref);
    }
  }
  return map;
}
