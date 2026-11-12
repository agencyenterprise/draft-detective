import { describe, expect, it } from 'vitest';
import { UserRole, type UserResponse } from '@/lib/generated-api';
import { wizardGate, type WizardGate } from './wizard-gate';

function user(hasKey: boolean | undefined): UserResponse {
  return {
    id: 'u1',
    email: 'author@example.com',
    name: 'Author',
    role: UserRole.User,
    show_experimental_features: false,
    has_openai_api_key: hasKey,
  };
}

/** The labels of the indicator's steps, and of those it ticks off. */
function indicator(gate: WizardGate) {
  if (gate.kind === 'loading') throw new Error('expected the gate to have decided');
  return {
    labels: gate.steps.map((s) => s.label),
    completed: gate.steps.filter((s) => s.completed).map((s) => s.label),
  };
}

describe('wizardGate when the deploy requires a key', () => {
  const requireApiKeyConfig = true;

  it('waits for the user before deciding, so nobody slips past the key form', () => {
    expect(wizardGate({ requireApiKeyConfig, user: undefined, currentStep: 1 })).toEqual({ kind: 'loading' });
  });

  it.each([false, undefined])('holds a user without a key (has_openai_api_key: %s) on the key form', (hasKey) => {
    for (const currentStep of [1, 2] as const) {
      const gate = wizardGate({ requireApiKeyConfig, user: user(hasKey), currentStep });
      expect(gate.kind).toBe('api-key');
      expect(gate).toMatchObject({ currentIndicatorStep: 1 });
      expect(indicator(gate).labels).toEqual(['API Key Setup', 'Your Document', 'Choose Assessments']);
      expect(indicator(gate).completed).not.toContain('API Key Setup');
    }
  });

  it('lets a user with a key into the wizard, one indicator step to the right', () => {
    const upload = wizardGate({ requireApiKeyConfig, user: user(true), currentStep: 1 });
    expect(upload).toMatchObject({ kind: 'wizard', currentIndicatorStep: 2 });
    expect(indicator(upload).completed).toEqual(['API Key Setup']);

    const assessments = wizardGate({ requireApiKeyConfig, user: user(true), currentStep: 2 });
    expect(assessments).toMatchObject({ kind: 'wizard', currentIndicatorStep: 3 });
    expect(indicator(assessments).completed).toEqual(['API Key Setup', 'Your Document']);
  });
});

describe('wizardGate when the deploy supplies the key', () => {
  const requireApiKeyConfig = false;

  it('opens the wizard straight away, without waiting for the user or asking for a key', () => {
    for (const u of [undefined, user(false)]) {
      const gate = wizardGate({ requireApiKeyConfig, user: u, currentStep: 1 });
      expect(gate).toMatchObject({ kind: 'wizard', currentIndicatorStep: 1 });
      expect(indicator(gate).labels).toEqual(['Your Document', 'Choose Assessments']);
    }
  });

  it('marks the upload done once the user reaches the assessments', () => {
    const gate = wizardGate({ requireApiKeyConfig, user: user(false), currentStep: 2 });
    expect(gate).toMatchObject({ kind: 'wizard', currentIndicatorStep: 2 });
    expect(indicator(gate).completed).toEqual(['Your Document']);
  });
});
