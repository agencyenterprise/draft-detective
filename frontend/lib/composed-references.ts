/**
 * Utility for composing reference data from split workflow states.
 *
 * The backend splits reference processing into two workflows:
 * - ReferenceExtraction: extracts references (id, text)
 * - ReferenceFileMatching: matches references to supporting files (reference_id, file_id)
 *
 * This module provides utilities to compose them into a unified view.
 */

import { ExtractedReference, MatchSource, ReferenceFileMatch } from './generated-api';

/**
 * A composed reference combining extraction and file matching data.
 */
export interface ComposedReference {
  id: string;
  text: string;
  file_id: string | null;
  source: MatchSource | null;
}

/**
 * Compose references from extraction state and file matching state.
 *
 * @param extractedRefs - References extracted from the document
 * @param matches - File matches from the matching workflow (optional)
 * @returns Array of composed references with file matching info
 */
export function composeReferences(
  extractedRefs: ExtractedReference[] | undefined,
  matches: ReferenceFileMatch[] | undefined,
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

  return extractedRefs.map((ref): ComposedReference => {
    const refId = ref.id ?? '';
    const match = matchByRefId.get(refId);

    return {
      id: refId,
      text: ref.text,
      file_id: match?.file_id ?? null,
      source: match?.source ?? null,
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
