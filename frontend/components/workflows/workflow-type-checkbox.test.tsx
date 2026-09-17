import { describe, expect, it } from 'vitest';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { WorkflowRunType, type WorkflowTypeDescription } from '@/lib/generated-api';
import { declaredIconName, WorkflowIcon } from './workflow-type-checkbox';

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
