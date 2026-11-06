import { afterEach, describe, expect, it } from 'vitest';
import { act } from 'react';
import { renderInto } from '@/lib/test-render';
import { useWebSearchConsent } from '@/lib/hooks/use-web-search-consent';

type Consent = ReturnType<typeof useWebSearchConsent>;

async function mount(projectId: string | null) {
  let latest!: Consent;
  function Probe() {
    latest = useWebSearchConsent(projectId);
    return null;
  }
  const view = await renderInto(<Probe />);
  return { view, current: () => latest };
}

afterEach(() => window.localStorage.clear());

describe('useWebSearchConsent', () => {
  it('remembers consent per project, so granting one leaves the others as they were', async () => {
    const a = await mount('project-a');
    expect(a.current()[0]).toBe(false);
    await act(async () => a.current()[1](true));
    expect(a.current()[0]).toBe(true);
    await a.view.unmount();

    // Another project never inherits project-a's consent.
    const b = await mount('project-b');
    expect(b.current()[0]).toBe(false);
    await act(async () => b.current()[1](false));
    expect(b.current()[0]).toBe(false);
    await b.view.unmount();

    // A fresh mount reads storage, as the workflow dialog does after the wizard.
    const again = await mount('project-a');
    expect(again.current()[0]).toBe(true);
    await again.view.unmount();
  });

  it('has no consent and stores nothing before a project exists', async () => {
    const { view, current } = await mount(null);
    await act(async () => current()[1](true));

    expect(current()[0]).toBe(false);
    expect(window.localStorage.getItem('web-search-consents')).toBeNull();
    await view.unmount();
  });
});
