import { afterEach, describe, expect, it } from 'vitest';
import { act } from 'react';
import { flush, renderInto, Rendered } from '@/lib/test-render';
import { ShareDialog } from './share-dialog';

let rendered: Rendered | null = null;
const unhandled: unknown[] = [];
const onUnhandled = (reason: unknown) => unhandled.push(reason);

async function openUnshared(onEnable: () => Promise<unknown>): Promise<void> {
  rendered = await renderInto(
    <ShareDialog
      open
      onOpenChange={() => undefined}
      shareStatus={null}
      isEnabling={false}
      isDisabling={false}
      onEnable={onEnable}
      onDisable={() => undefined}
    />,
  );
  await flush();
}

/** The dialog renders in a portal, so the button is looked up from the body. */
async function click(label: string): Promise<void> {
  const button = [...document.body.querySelectorAll<HTMLElement>('button')].find((el) =>
    el.textContent?.includes(label),
  );
  if (!button) throw new Error(`no "${label}" in: ${document.body.textContent}`);
  await act(async () => button.click());
  await flush();
}

afterEach(async () => {
  process.off('unhandledRejection', onUnhandled);
  unhandled.length = 0;
  await rendered?.unmount();
  rendered = null;
});

describe('ShareDialog', () => {
  it('a failed enable leaves no unhandled rejection, since the caller already reported it', async () => {
    process.on('unhandledRejection', onUnhandled);
    // A plain function, not vi.fn(): a mock attaches its own handler to the promise it returns.
    let calls = 0;
    await openUnshared(() => {
      calls += 1;
      return Promise.reject(new Error('enable failed'));
    });

    await click('Enable Sharing');
    // Unhandled rejections are reported after a macrotask turn.
    await flush();
    await flush();

    expect(calls).toBe(1);
    expect(unhandled).toEqual([]);
  });
});
