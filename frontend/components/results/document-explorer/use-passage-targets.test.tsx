import { SeverityEnum, WorkflowRunType, type Issue } from '@/lib/generated-api';
import { renderInto, type Rendered } from '@/lib/test-render';
import { act, useRef } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { usePassageTargets } from './use-passage-targets';

function issue(id: string, line: number, passage: string | null): Issue {
  return {
    id,
    project_id: 'p',
    workflow_run_id: 'r',
    issue_hash: id,
    title: id,
    description: '',
    severity: SeverityEnum.Low,
    workflow_type: WorkflowRunType.WritingConsistency,
    start_line: line,
    end_line: line,
    created_at: new Date('2026-01-01T00:00:00Z'),
    updated_at: new Date('2026-01-01T00:00:00Z'),
    edits: [],
    passage: passage
      ? { original_text: passage, display_text: passage, display_occurrence: 0, start_line: line, end_line: line }
      : null,
  };
}

const outer = issue('outer', 3, 'Porters’ Five Forces model');
const inner = issue('inner', 3, 'Five Forces model');
const wholeLine = issue('whole-line', 5, null);
const ISSUES = [outer, inner, wholeLine];

// Where each passage is laid out, by its text: jsdom lays nothing out.
const BOXES: Record<string, DOMRect> = {
  'Porters’ Five Forces model': new DOMRect(0, 0, 100, 10),
  'Five Forces model': new DOMRect(40, 0, 60, 10),
};

function Harness({ activeId, onSelect }: { activeId: string | null; onSelect: (issue: Issue | null) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const { handlers } = usePassageTargets(ref, 'markdown', ISSUES, activeId, onSelect);
  return (
    <div ref={ref} {...handlers}>
      <p data-block-owner="" data-line-start="3" data-line-end="3">
        We apply <b>Porters’ Five Forces model</b> to each concept.
      </p>
      <p data-block-owner="" data-line-start="5" data-line-end="5" data-line-targets="whole-line">
        A paragraph about its whole self.
      </p>
      <div data-margin-layer="">
        <p data-block-owner="" data-line-start="3" data-line-end="3">
          A note.
        </p>
      </div>
    </div>
  );
}

let rendered: Rendered | null = null;

beforeEach(() => {
  vi.stubGlobal('CSS', { highlights: new Map() });
  vi.stubGlobal('Highlight', class {});
  // jsdom's Range has no layout, so each passage is given its box by its text.
  Object.defineProperty(Range.prototype, 'getClientRects', {
    configurable: true,
    value: function (this: Range) {
      const box = BOXES[this.toString()];
      return (box ? [box] : []) as unknown as DOMRectList;
    },
  });
});

afterEach(async () => {
  await rendered?.unmount();
  rendered = null;
  delete (Range.prototype as { getClientRects?: unknown }).getClientRects;
  vi.unstubAllGlobals();
});

async function clickAt(activeId: string | null, selector: string, x: number) {
  const onSelect = vi.fn();
  rendered = await renderInto(<Harness activeId={activeId} onSelect={onSelect} />);
  const target = rendered.container.querySelector(selector)!;
  await act(async () => {
    target.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: x, clientY: 5 }));
  });
  return onSelect;
}

describe('a click in the document', () => {
  it('opens the issue whose passage it lands on', async () => {
    expect(await clickAt(null, 'b', 20)).toHaveBeenCalledWith(outer);
  });

  it('opens the narrowest of nested passages, then steps outward, then closes', async () => {
    expect(await clickAt(null, 'b', 60)).toHaveBeenCalledWith(inner);
    await rendered!.unmount();
    expect(await clickAt('inner', 'b', 60)).toHaveBeenCalledWith(outer);
    await rendered!.unmount();
    expect(await clickAt('outer', 'b', 60)).toHaveBeenCalledWith(null);
  });

  it('opens a whole-line issue from its paragraph', async () => {
    expect(await clickAt(null, '[data-line-targets]', 20)).toHaveBeenCalledWith(wholeLine);
  });

  it('leaves the open issue alone on text that is no target', async () => {
    expect(await clickAt('outer', 'p', 300)).not.toHaveBeenCalled();
  });

  it('leaves clicks in the margin to the notes', async () => {
    expect(await clickAt(null, '[data-margin-layer] p', 20)).not.toHaveBeenCalled();
  });
});
