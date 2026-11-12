import { act, type ReactNode } from 'react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { flush, renderInto, testQueryClient, withQueryClient, type Rendered } from '@/lib/test-render';

const mocks = vi.hoisted(() => ({ me: vi.fn() }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  getCurrentUserInfoApiUsersMeGet: mocks.me,
}));
vi.mock('next-auth/react', () => ({ useSession: () => ({ status: 'authenticated' }) }));
// The page's chrome and steps are covered elsewhere; stand-ins show which step the page chose.
vi.mock('@/components/results/app-bar', () => ({ AppBar: () => null }));
vi.mock('@/components/analysis-wizard/step-api-key-config', () => ({ StepApiKeyConfig: () => <p>api-key-step</p> }));
vi.mock('@/components/analysis-wizard/wizard-context', () => ({
  WizardProvider: ({ children }: { children: ReactNode }) => children,
  useWizard: () => ({ currentStep: 1, nextStep: () => {} }),
}));
vi.mock('@/components/analysis-wizard/step-upload', () => ({ StepUpload: () => <p>upload-step</p> }));

// The page reads the flag when its module loads, so set it before importing the page.
let New: typeof import('./page').default;
beforeAll(async () => {
  vi.stubEnv('NEXT_PUBLIC_REQUIRE_OPENAI_API_KEY_CONFIG', 'true');
  New = (await import('./page')).default;
});

let view: Rendered | undefined;
afterEach(async () => {
  await view?.unmount();
  view = undefined;
  vi.clearAllMocks();
});

describe('/new on a deploy that requires a key', () => {
  it('offers a retry when the user lookup fails, and moves on once it succeeds', async () => {
    mocks.me.mockRejectedValueOnce(new Error('Internal Server Error'));
    mocks.me.mockResolvedValueOnce({ id: 'u-1', has_openai_api_key: false });
    view = await renderInto(withQueryClient(testQueryClient(), <New />));
    await flush();

    const retry = [...view.container.querySelectorAll('button')].find((b) => b.textContent === 'Try again');
    expect(retry).toBeDefined();

    await act(async () => retry!.click());
    await flush();
    expect(mocks.me).toHaveBeenCalledTimes(2);
    expect(view.container.textContent).toContain('api-key-step');
  });
});
