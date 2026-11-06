import { afterEach, describe, expect, it } from 'vitest';
import { act } from 'react';
import { renderInto } from '@/lib/test-render';
import { useLocalStorage } from '@/lib/hooks/use-local-storage';

type Stored = ReturnType<typeof useLocalStorage<string[]>>;

function Probe({ onRender }: { onRender: (stored: Stored) => void }) {
  onRender(useLocalStorage<string[]>('picked', ['default']));
  return null;
}

async function mount() {
  let latest!: Stored;
  const view = await renderInto(<Probe onRender={(stored) => (latest = stored)} />);
  return { view, current: () => latest };
}

afterEach(() => window.localStorage.clear());

describe('useLocalStorage', () => {
  it('starts from the default when nothing is stored', async () => {
    const { view, current } = await mount();
    expect(current()[0]).toEqual(['default']);
    await view.unmount();
  });

  it('falls back to the default when the stored value is not JSON', async () => {
    window.localStorage.setItem('picked', '{broken');
    const { view, current } = await mount();
    expect(current()[0]).toEqual(['default']);
    await view.unmount();
  });

  it('keeps a set value across a remount', async () => {
    const first = await mount();
    await act(async () => first.current()[1](['a', 'b']));
    expect(first.current()[0]).toEqual(['a', 'b']);
    await first.view.unmount();

    const second = await mount();
    expect(second.current()[0]).toEqual(['a', 'b']);
    await second.view.unmount();
  });
});
