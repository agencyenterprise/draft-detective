import { act } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { LineRange } from '@/lib/stores/document-explorer-store';
import { renderInto, type Rendered } from '@/lib/test-render';
import { parseLineHash, useLineHashNavigation } from './line-hash';

describe('parseLineHash', () => {
  it.each([
    ['#L5', [5, 5]],
    ['#L5-15', [5, 15]],
    // A range written backwards still selects the same lines.
    ['#L15-5', [5, 15]],
    ['#L7-7', [7, 7]],
  ])('reads %s as lines %j', (hash, range) => {
    expect(parseLineHash(hash)).toEqual(range);
  });

  it.each(['', 'L5', '#', '#L', '#L5-', '#l5', '#L5x', '#L5-15-20', '#Lfive', '#comments'])(
    'ignores %j, which is not a line link',
    (hash) => {
      expect(parseLineHash(hash)).toBeNull();
    },
  );
});

function Probe({ onSelectRange }: { onSelectRange: (range: LineRange) => void }) {
  useLineHashNavigation(onSelectRange);
  return null;
}

async function goTo(hash: string): Promise<void> {
  await act(async () => {
    window.location.hash = hash;
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  });
}

describe('useLineHashNavigation', () => {
  let rendered: Rendered | null = null;

  afterEach(async () => {
    await rendered?.unmount();
    rendered = null;
    window.location.hash = '';
  });

  it('selects the lines of the hash the page opened on', async () => {
    window.location.hash = '#L5-15';
    const onSelectRange = vi.fn();

    rendered = await renderInto(<Probe onSelectRange={onSelectRange} />);

    expect(onSelectRange).toHaveBeenCalledExactlyOnceWith([5, 15]);
  });

  it('selects nothing when the page opened without a line link', async () => {
    window.location.hash = '#comments';
    const onSelectRange = vi.fn();

    rendered = await renderInto(<Probe onSelectRange={onSelectRange} />);

    expect(onSelectRange).not.toHaveBeenCalled();
  });

  it('follows the hash as it changes', async () => {
    const onSelectRange = vi.fn();
    rendered = await renderInto(<Probe onSelectRange={onSelectRange} />);

    await goTo('#L3');
    await goTo('#L8-9');

    expect(onSelectRange.mock.calls).toEqual([[[3, 3]], [[8, 9]]]);
  });

  it('does not select the same link again when the callback changes', async () => {
    // The explorer passes a new callback when its own state changes; reselecting the
    // hash's lines then would undo a selection the reader has since made.
    window.location.hash = '#L5';
    const first = vi.fn();
    const second = vi.fn();
    rendered = await renderInto(<Probe onSelectRange={first} />);

    await rendered.rerender(<Probe onSelectRange={second} />);

    expect(first).toHaveBeenCalledOnce();
    expect(second).not.toHaveBeenCalled();
  });

  it('selects a line link again after the hash moved away from it', async () => {
    // Back from an edited URL (#L5, then none, then Back to #L5) lands on the link again.
    window.location.hash = '#L5';
    const onSelectRange = vi.fn();
    rendered = await renderInto(<Probe onSelectRange={onSelectRange} />);

    await goTo('');
    await goTo('#L5');

    expect(onSelectRange.mock.calls).toEqual([[[5, 5]], [[5, 5]]]);
  });

  it('stops listening once unmounted', async () => {
    const onSelectRange = vi.fn();
    rendered = await renderInto(<Probe onSelectRange={onSelectRange} />);
    await rendered.unmount();
    rendered = null;

    await goTo('#L4');

    expect(onSelectRange).not.toHaveBeenCalled();
  });
});
