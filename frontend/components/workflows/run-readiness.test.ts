import { describe, expect, it } from 'vitest';
import { WorkflowRunType, type WorkflowTypeDescription } from '@/lib/generated-api';
import { runReadiness, RUN_BLOCKER_MESSAGES } from './run-readiness';

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

function readiness(overrides: Partial<Parameters<typeof runReadiness>[0]> = {}) {
  return runReadiness({
    selectedTypes: [WorkflowRunType.ActiveVoice],
    webSearchConsent: false,
    workflowTypes: METADATA,
    metadataPending: false,
    metadataFailed: false,
    ...overrides,
  });
}

describe('runReadiness', () => {
  it('is ready with a valid selection and nothing else to say', () => {
    expect(readiness()).toEqual({ blocker: null, messages: [], ready: true });
  });

  it('holds a pristine dialog with nothing selected, without any validation having run', () => {
    const result = readiness({ selectedTypes: [] });
    expect(result.ready).toBe(false);
    expect(result.messages).toEqual([RUN_BLOCKER_MESSAGES['none-selected']]);
  });

  it('holds a pristine dialog silently: the button waits, the message does not show yet', () => {
    const result = readiness({ selectedTypes: [], pristine: true });
    expect(result.ready).toBe(false);
    expect(result.blocker).toBe('none-selected');
    expect(result.messages).toEqual([]);
  });

  it('says nothing on a pristine form that is ready either', () => {
    expect(readiness({ pristine: true })).toEqual({ blocker: null, messages: [], ready: true });
  });

  it('holds a preselected web-search assessment until consent is given', () => {
    const selectedTypes = [WorkflowRunType.ReferenceValidationV2];
    expect(readiness({ selectedTypes }).blocker).toBe('consent-missing');
    expect(readiness({ selectedTypes, webSearchConsent: true }).ready).toBe(true);
  });

  it('holds the button while the metadata is still loading, even with a selection', () => {
    const result = readiness({ workflowTypes: [], metadataPending: true });
    expect(result.ready).toBe(false);
    expect(result.messages).toEqual([RUN_BLOCKER_MESSAGES['metadata-pending']]);
  });

  it('lists a field error in the footer and treats it as blocking', () => {
    const result = readiness({ fieldErrors: ['Document publication date is required'] });
    expect(result.blocker).toBeNull();
    expect(result.ready).toBe(false);
    expect(result.messages).toEqual(['Document publication date is required']);
  });

  it('shows the blocker before a field error when both apply', () => {
    const result = readiness({ selectedTypes: [], fieldErrors: ['Document publication date is required'] });
    expect(result.messages).toEqual([RUN_BLOCKER_MESSAGES['none-selected'], 'Document publication date is required']);
  });
});
