import { describe, expect, it } from 'vitest';

import { buildReferenceByFileIdMap, composeReferences } from './composed-references';
import { MatchSource } from './generated-api';

const refs = [
  { id: 'r1', text: 'Smith, 2020' },
  { id: 'r2', text: 'Jones, 2021' },
  { id: 'r3', text: 'Lee, 2022' },
];

describe('composeReferences', () => {
  it('returns nothing until references have been extracted', () => {
    expect(composeReferences(undefined, undefined)).toEqual([]);
    expect(composeReferences([], [{ reference_id: 'r1', file_id: 'f1' }])).toEqual([]);
  });

  it('attaches each match to its reference, in extraction order', () => {
    const matches = [
      { reference_id: 'r3', file_id: 'f3', source: MatchSource.ManualUpload },
      { reference_id: 'r1', file_id: 'f1', source: MatchSource.AutoMatched },
    ];

    expect(composeReferences(refs, matches)).toEqual([
      { id: 'r1', text: 'Smith, 2020', file_id: 'f1', source: MatchSource.AutoMatched },
      { id: 'r2', text: 'Jones, 2021', file_id: null, source: null },
      { id: 'r3', text: 'Lee, 2022', file_id: 'f3', source: MatchSource.ManualUpload },
    ]);
  });

  it('lists every reference as unmatched before matching has run', () => {
    expect(composeReferences(refs, undefined).map((r) => [r.id, r.file_id, r.source])).toEqual([
      ['r1', null, null],
      ['r2', null, null],
      ['r3', null, null],
    ]);
  });

  it('ignores a match for a reference that is no longer extracted', () => {
    const composed = composeReferences(refs, [{ reference_id: 'gone', file_id: 'f9' }]);

    expect(composed.map((r) => r.file_id)).toEqual([null, null, null]);
  });
});

describe('buildReferenceByFileIdMap', () => {
  it('maps each matched file to the reference it backs and skips unmatched references', () => {
    const composed = composeReferences(refs, [
      { reference_id: 'r1', file_id: 'f1' },
      { reference_id: 'r3', file_id: 'f3' },
    ]);

    const byFile = buildReferenceByFileIdMap(composed);

    expect([...byFile.keys()]).toEqual(['f1', 'f3']);
    expect(byFile.get('f3')?.text).toBe('Lee, 2022');
  });
});
