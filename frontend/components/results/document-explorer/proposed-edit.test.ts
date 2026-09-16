import { describe, expect, it } from 'vitest';
import { isDeletion, type ProposedEdit } from './proposed-edit';

function edit(replacement_text: string): ProposedEdit {
  return {
    id: 'e1',
    issue_id: 'i1',
    original_text: 'the quoted text',
    replacement_text,
    start_line: 4,
    end_line: 4,
    rationale: 'Because.',
    status: 'proposed',
  };
}

describe('isDeletion', () => {
  it('is true only for exactly the empty string, as the backend defines a deletion', () => {
    expect(isDeletion(edit(''))).toBe(true);
  });

  it('treats a whitespace-only replacement as a real replacement', () => {
    expect(isDeletion(edit(' '))).toBe(false);
    expect(isDeletion(edit('\n'))).toBe(false);
  });

  it('is false for ordinary replacements', () => {
    expect(isDeletion(edit('the corrected text'))).toBe(false);
  });
});
