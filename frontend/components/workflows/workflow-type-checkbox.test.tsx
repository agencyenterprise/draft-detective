import { describe, expect, it } from 'vitest';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { WorkflowGate, WorkflowRunType, type WorkflowTypeDescription } from '@/lib/generated-api';
import { declaredIconName, WorkflowIcon, WorkflowTypeCheckbox } from './workflow-type-checkbox';

function workflowType(overrides: Partial<WorkflowTypeDescription> = {}): WorkflowTypeDescription {
  return {
    type: WorkflowRunType.ActiveVoice,
    name: 'Active Voice & Clear Actors',
    description: 'Passive sentences that hide who acts.',
    needs_web_search: false,
    is_experimental: true,
    is_internal: false,
    category: 'language',
    gates: [],
    ...overrides,
  };
}

describe('declaredIconName', () => {
  it('accepts a name lucide ships', () => {
    expect(declaredIconName('pen-line')).toBe('pen-line');
  });

  it('rejects names lucide does not know, so the caller falls back', () => {
    expect(declaredIconName('PenLine')).toBeNull();
    expect(declaredIconName('no-such-icon')).toBeNull();
  });

  it('treats a missing declaration as none', () => {
    expect(declaredIconName(undefined)).toBeNull();
    expect(declaredIconName(null)).toBeNull();
    expect(declaredIconName('')).toBeNull();
  });
});

describe('WorkflowTypeCheckbox badges', () => {
  function markup(overrides: Partial<WorkflowTypeDescription>): string {
    return renderToStaticMarkup(
      <WorkflowTypeCheckbox workflowType={workflowType(overrides)} checked={false} onCheckedChange={() => undefined} />,
    );
  }

  it('shows the proposed-edits badge only for workflows that propose edits', () => {
    expect(markup({ proposes_edits: true })).toContain('Proposed Edits');
    expect(markup({ proposes_edits: false })).not.toContain('Proposed Edits');
  });

  it('keeps the alpha and web-search badges alongside it', () => {
    const html = markup({ proposes_edits: true, is_experimental: true, needs_web_search: true });
    expect(html).toContain('Alpha');
    expect(html).toContain('Web Search');
    expect(html).toContain('Proposed Edits');
  });

  it('names the reference gate for workflows that need full-text sources', () => {
    expect(markup({ gates: [WorkflowGate.ReferenceReview] })).toContain('Needs Full Text References');
    expect(markup({ gates: [] })).not.toContain('Needs Full Text References');
  });

  it('shows the run-time estimate as text, since the value is the point', () => {
    const html = renderToStaticMarkup(
      <WorkflowTypeCheckbox
        workflowType={workflowType()}
        checked={false}
        onCheckedChange={() => undefined}
        estimatedSeconds={150}
      />,
    );
    expect(html).toContain('~3 min');
  });

  it('renders the description in the row', () => {
    const html = markup({ description: 'A long sentence about what the assessment does.' });
    expect(html).toContain('A long sentence about what the assessment does.');
  });
});

describe('WorkflowIcon', () => {
  it('draws a declared lucide icon dynamically rather than from the static map', () => {
    // DynamicIcon loads the icon after mount, so a static render carries no
    // svg yet; what matters is that the map's fallback was not used.
    const markup = renderToStaticMarkup(<WorkflowIcon workflowType={workflowType({ icon: 'pen-line' })} />);

    expect(markup).not.toContain('lucide-file-text');
  });

  it('falls back to the default icon for a skill-declared workflow with no usable icon', () => {
    const markup = renderToStaticMarkup(<WorkflowIcon workflowType={workflowType({ icon: 'no-such-icon' })} />);

    expect(markup).toContain('lucide-file-text');
  });

  it('keeps the hand-written mapping for workflows that declare nothing', () => {
    const markup = renderToStaticMarkup(
      <WorkflowIcon workflowType={workflowType({ type: WorkflowRunType.AdvocacyToneV2 })} className="size-4" />,
    );

    expect(markup).toContain('lucide-message-square-warning');
    expect(markup).toContain('size-4');
  });
});
