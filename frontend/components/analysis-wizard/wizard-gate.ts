import type { UserResponse } from '@/lib/generated-api';

export interface IndicatorStep {
  label: string;
  completed: boolean;
}

interface WizardGateInput {
  /** Whether this deploy makes users save their own OpenAI key before starting a project. */
  requireApiKeyConfig: boolean;
  /** The signed-in user, `undefined` until the lookup resolves. */
  user: UserResponse | undefined;
  /** Whether the user lookup failed. It doesn't retry on its own, so the page must offer a retry. */
  userLookupFailed: boolean;
  /** The wizard's own step: 1 for the upload, 2 for the assessments. */
  currentStep: 1 | 2;
}

export type WizardGate =
  | { kind: 'loading' }
  | { kind: 'lookup-failed' }
  | { kind: 'api-key'; steps: IndicatorStep[]; currentIndicatorStep: number }
  | { kind: 'wizard'; steps: IndicatorStep[]; currentIndicatorStep: number };

/**
 * Which screen the new-project wizard shows, and the step indicator above it.
 *
 * When the deploy requires a key, the key form comes first and blocks the rest
 * until the user has one. Its step stays in the indicator once completed, so the
 * wizard's own steps move one place to the right.
 */
export function wizardGate({ requireApiKeyConfig, user, userLookupFailed, currentStep }: WizardGateInput): WizardGate {
  // Gating on `user === undefined` rather than `isLoading` renders the same on the
  // server, which has no user, and on the client's first render, which is fetching.
  // A failed lookup leaves `user` undefined for good, so it gets its own screen
  // rather than the spinner. `isError` is false on the server and the first render.
  if (requireApiKeyConfig && user === undefined) return { kind: userLookupFailed ? 'lookup-failed' : 'loading' };

  const apiKeyConfigured = user?.has_openai_api_key ?? false;
  const apiKeySteps = requireApiKeyConfig ? [{ label: 'API Key Setup', completed: apiKeyConfigured }] : [];
  const steps = [
    ...apiKeySteps,
    { label: 'Your Document', completed: currentStep > 1 },
    { label: 'Choose Assessments', completed: currentStep > 2 },
  ];

  if (requireApiKeyConfig && !apiKeyConfigured) return { kind: 'api-key', steps, currentIndicatorStep: 1 };
  return { kind: 'wizard', steps, currentIndicatorStep: currentStep + apiKeySteps.length };
}
