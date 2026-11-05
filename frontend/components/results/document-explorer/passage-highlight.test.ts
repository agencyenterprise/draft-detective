import { SeverityEnum, WorkflowRunType, type Issue, type IssuePassageRead } from '@/lib/generated-api';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  PASSAGE_HIGHLIGHT_NAME,
  blockKeepsUnderline,
  locatePassages,
  paintPassages,
  passageSeverity,
  selectedPassageHighlightName,
  washesBlock,
} from './passage-highlight';

function passage(overrides: Partial<IssuePassageRead> = {}): IssuePassageRead {
  return {
    original_text: 'certainly',
    display_text: 'certainly',
    display_occurrence: 0,
    start_line: 3,
    end_line: 3,
    ...overrides,
  };
}

function issue(overrides: Partial<Issue> = {}): Issue {
  return {
    id: 'issue-1',
    project_id: 'project-1',
    workflow_run_id: 'run-1',
    issue_hash: 'hash-1',
    title: 'Trigger word',
    description: 'Certainty language',
    severity: SeverityEnum.Medium,
    workflow_type: WorkflowRunType.AdvocacyToneV2,
    start_line: 3,
    end_line: 3,
    created_at: new Date('2026-01-01T00:00:00Z'),
    updated_at: new Date('2026-01-01T00:00:00Z'),
    edits: [],
    passage: null,
    ...overrides,
  };
}

/** A rendered document with one block per line, as the view lays it out. */
function documentWith(lines: Record<number, string>): HTMLElement {
  const root = document.createElement('div');
  for (const [line, html] of Object.entries(lines)) {
    const block = document.createElement('p');
    block.setAttribute('data-line-start', line);
    block.setAttribute('data-line-end', line);
    block.innerHTML = html;
    root.appendChild(block);
  }
  return root;
}

class FakeHighlight {
  readonly ranges: Range[];
  priority = 0;

  constructor(...ranges: Range[]) {
    this.ranges = ranges;
  }
}

function stubHighlightApi(): Map<string, FakeHighlight> {
  const highlights = new Map<string, FakeHighlight>();
  vi.stubGlobal('CSS', { highlights });
  vi.stubGlobal('Highlight', FakeHighlight);
  return highlights;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('locatePassages', () => {
  it('finds each passage on its own line, and skips issues without one or whose words are gone', () => {
    stubHighlightApi();
    const page = documentWith({ 3: 'This will <strong>certainly</strong> work.', 5: 'Another line.' });
    const found = issue({ id: 'found', passage: passage() });
    const whole = issue({ id: 'whole-line' });
    const gone = issue({ id: 'gone', passage: passage({ display_text: 'never written' }) });

    const located = locatePassages(page, [found, whole, gone]);

    expect([...located.keys()]).toEqual(['found']);
    expect(located.get('found')?.toString()).toBe('certainly');
  });

  it('locates nothing where the browser cannot paint a highlight, so every issue keeps its block marks', () => {
    const page = documentWith({ 3: 'This will certainly work.' });
    expect(locatePassages(page, [issue({ passage: passage() })]).size).toBe(0);
  });
});

describe('block marks', () => {
  const range = new Range();

  it('drops the block underline only when every issue on it is marked on its passage', () => {
    const marked = issue({ id: 'marked' });
    const lineLevel = issue({ id: 'line-level' });

    expect(blockKeepsUnderline([marked], new Map([['marked', range]]))).toBe(false);
    expect(blockKeepsUnderline([marked, lineLevel], new Map([['marked', range]]))).toBe(true);
  });

  it('washes a selected block unless every open issue is marked on its passage', () => {
    const open = issue({ id: 'open' });

    expect(washesBlock(true, [open], new Map([['open', range]]))).toBe(false);
    expect(washesBlock(true, [open], new Map())).toBe(true);
    // Selected lines with no issue open in particular: the block is what was picked.
    expect(washesBlock(true, [], new Map([['open', range]]))).toBe(true);
    expect(washesBlock(false, [open], new Map())).toBe(false);
  });
});

describe('paintPassages', () => {
  it('dots every located passage and washes the open ones in their severity colour, under the edits', () => {
    const highlights = stubHighlightApi();
    const page = documentWith({ 3: 'This will certainly work.', 4: 'We must act.' });
    const rest = issue({ id: 'rest', passage: passage() });
    const open = issue({
      id: 'open',
      severity: SeverityEnum.High,
      start_line: 4,
      end_line: 4,
      passage: passage({ display_text: 'must', start_line: 4, end_line: 4 }),
    });
    const located = locatePassages(page, [rest, open]);

    paintPassages(located, [open], (severity) => severity);

    expect(highlights.get(PASSAGE_HIGHLIGHT_NAME)?.ranges.map(String)).toEqual(['certainly', 'must']);
    const washed = highlights.get(selectedPassageHighlightName(SeverityEnum.High));
    expect(washed?.ranges.map(String)).toEqual(['must']);
    expect(washed?.priority).toBeLessThan(2);
    expect(highlights.has(selectedPassageHighlightName(SeverityEnum.Medium))).toBe(false);
  });

  it('washes every finding in the medium colour when the project does not group by severity', () => {
    expect(passageSeverity(SeverityEnum.High, false)).toBe(SeverityEnum.Medium);
    expect(passageSeverity(SeverityEnum.None, false)).toBe(SeverityEnum.None);
    expect(passageSeverity(SeverityEnum.High, true)).toBe(SeverityEnum.High);
  });
});
