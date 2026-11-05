import { SeverityEnum, WorkflowRunType, type Issue } from '@/lib/generated-api';
import { describe, expect, it } from 'vitest';
import { issuesAtPoint, lineTargets, nextTarget, type Box } from './passage-targets';

const box = (left: number, top: number, right: number, bottom: number): Box => ({ left, top, right, bottom });

function issue(id: string, start: number, end: number, severity: SeverityEnum = SeverityEnum.Low): Issue {
  return {
    id,
    project_id: 'p',
    workflow_run_id: 'r',
    issue_hash: id,
    title: id,
    description: '',
    severity,
    workflow_type: WorkflowRunType.WritingConsistency,
    start_line: start,
    end_line: end,
    created_at: new Date('2026-01-01T00:00:00Z'),
    updated_at: new Date('2026-01-01T00:00:00Z'),
    edits: [],
    passage: null,
  };
}

describe('issuesAtPoint', () => {
  // "Porters' Five Forces model" holds "Five Forces model"; the second wraps onto a new line.
  const boxes = new Map([
    ['outer', { boxes: [box(830, 370, 920, 390), box(200, 395, 290, 415)], length: 26 }],
    ['inner', { boxes: [box(890, 370, 920, 390), box(200, 395, 290, 415)], length: 17 }],
    ['elsewhere', { boxes: [box(200, 100, 400, 120)], length: 30 }],
  ]);

  it('lists the passages under the point, the narrowest first', () => {
    expect(issuesAtPoint(boxes, 900, 380)).toEqual(['inner', 'outer']);
    expect(issuesAtPoint(boxes, 840, 380)).toEqual(['outer']);
    expect(issuesAtPoint(boxes, 250, 405)).toEqual(['inner', 'outer']);
  });

  it('finds nothing between passages', () => {
    expect(issuesAtPoint(boxes, 600, 250)).toEqual([]);
  });
});

describe('nextTarget', () => {
  it('opens the narrowest, steps through the rest on the same words, then closes', () => {
    expect(nextTarget(['inner', 'outer'], null)).toBe('inner');
    expect(nextTarget(['inner', 'outer'], 'inner')).toBe('outer');
    expect(nextTarget(['inner', 'outer'], 'outer')).toBeNull();
    expect(nextTarget(['inner', 'outer'], 'some-other-issue')).toBe('inner');
    expect(nextTarget([], 'inner')).toBeNull();
  });
});

describe('lineTargets', () => {
  const rank = (i: Issue) => ['none', 'low', 'medium', 'high'].indexOf(i.severity);

  it('is the issues without a located passage that start in the paragraph, most severe first', () => {
    const passage = issue('passage', 10, 10);
    const low = issue('low', 10, 10);
    const high = issue('high', 10, 10, SeverityEnum.High);
    const spread = issue('spread', 4, 12);

    const targets = lineTargets([passage, low, high, spread], new Set(['passage']), 10, 10, rank);

    // `spread` covers line 10 too, but is opened from line 4, where it starts.
    expect(targets.map((i) => i.id)).toEqual(['high', 'low']);
    expect(lineTargets([spread], new Set(), 4, 4, rank).map((i) => i.id)).toEqual(['spread']);
  });
});
