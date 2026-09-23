import { describe, expect, it } from 'vitest';
import { WorkflowRunType, type WorkflowTypeDescription } from '@/lib/generated-api';
import { startBlocker } from './utils';

function workflowType(type: WorkflowRunType, needsWebSearch: boolean): WorkflowTypeDescription {
  return {
    type,
    name: type,
    description: '',
    needs_web_search: needsWebSearch,
    is_experimental: false,
    is_internal: false,
    category: 'test',
    gates: [],
  };
}

const METADATA = [
  workflowType(WorkflowRunType.ReferenceValidationV2, true),
  workflowType(WorkflowRunType.ActiveVoice, false),
];

function blocker(overrides: Partial<Parameters<typeof startBlocker>[0]> = {}) {
  return startBlocker({
    selectedTypes: [WorkflowRunType.ActiveVoice],
    workflowTypes: METADATA,
    metadataPending: false,
    metadataFailed: false,
    webSearchConsent: false,
    ...overrides,
  });
}

describe('startBlocker', () => {
  it('lets a selection without web search start without consent', () => {
    expect(blocker()).toBeNull();
  });

  it('waits for the workflow metadata before judging any selection', () => {
    // Without the metadata every needs_web_search flag reads as false, so a
    // web-searching assessment would otherwise start with no consent asked.
    expect(
      blocker({ selectedTypes: [WorkflowRunType.ReferenceValidationV2], workflowTypes: [], metadataPending: true }),
    ).toBe('metadata-pending');
    expect(blocker({ workflowTypes: [], metadataPending: true })).toBe('metadata-pending');
  });

  it('treats a failed metadata load as not ready rather than as consent-free', () => {
    expect(
      blocker({ selectedTypes: [WorkflowRunType.ReferenceValidationV2], workflowTypes: [], metadataFailed: true }),
    ).toBe('metadata-failed');
  });

  it('needs at least one assessment', () => {
    expect(blocker({ selectedTypes: [] })).toBe('none-selected');
  });

  it('needs consent when any selected assessment searches the web', () => {
    const selectedTypes = [WorkflowRunType.ActiveVoice, WorkflowRunType.ReferenceValidationV2];
    expect(blocker({ selectedTypes })).toBe('consent-missing');
    expect(blocker({ selectedTypes, webSearchConsent: true })).toBeNull();
  });

  it('reports readiness before selection, and selection before consent', () => {
    expect(blocker({ selectedTypes: [], metadataPending: true })).toBe('metadata-pending');
    expect(blocker({ selectedTypes: [], webSearchConsent: false })).toBe('none-selected');
  });
});
