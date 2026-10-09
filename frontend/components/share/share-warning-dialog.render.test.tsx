import { afterEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { flush, renderInto, Rendered } from '@/lib/test-render';
import { DEFAULT_FILTER } from '@/lib/stores/document-explorer-store';
import { ShareWarningDialog } from './share-warning-dialog';

let rendered: Rendered | null = null;

type Options = { isProjectPublic?: boolean; linksAvailable?: boolean };

async function open({ isProjectPublic = false, linksAvailable = true }: Options = {}) {
  const onDownload = vi.fn();
  rendered = await renderInto(
    <ShareWarningDialog
      open
      onOpenChange={() => undefined}
      isProjectPublic={isProjectPublic}
      isEnablingShare={false}
      isDownloading={false}
      filters={DEFAULT_FILTER}
      counts={{ issues: 3, edits: 2 }}
      linksAvailable={linksAvailable}
      onDownload={onDownload}
    />,
  );
  await flush();
  return onDownload;
}

/** The dialog renders in a portal, so everything is looked up from the body. */
function control(label: string): HTMLElement {
  const found = [...document.body.querySelectorAll<HTMLElement>('button, [role="checkbox"], label')].find((el) =>
    el.textContent?.includes(label),
  );
  if (!found) throw new Error(`no "${label}" in: ${document.body.textContent}`);
  return found;
}

async function click(label: string): Promise<void> {
  await act(async () => control(label).click());
  await flush();
}

afterEach(async () => {
  await rendered?.unmount();
  rendered = null;
});

describe('ShareWarningDialog', () => {
  it('offers no add-in export any more', async () => {
    await open();

    expect(document.body.textContent).not.toContain('add-in');
  });

  it('a private project downloads plain comments, with edits, by default', async () => {
    const onDownload = await open();
    await click('Download');

    expect(onDownload).toHaveBeenCalledWith('comments', { includeEdits: true });
  });

  it('a public project links its comments', async () => {
    const onDownload = await open({ isProjectPublic: true });
    await click('Download');

    expect(onDownload).toHaveBeenCalledWith('comments-with-links', { includeEdits: true });
  });

  it('asking for links on a private project links them', async () => {
    const onDownload = await open();
    await click('Link comments to Draft Detective');
    await click('Download');

    expect(onDownload).toHaveBeenCalledWith('comments-with-links', { includeEdits: true });
  });

  it('never asks for links the backend would drop', async () => {
    const onDownload = await open({ isProjectPublic: true, linksAvailable: false });
    await click('Download');

    expect(onDownload).toHaveBeenCalledWith('comments', { includeEdits: true });
    expect(document.body.textContent).toContain('only added when exporting the current revision');
  });

  it('edits can be left out', async () => {
    const onDownload = await open();
    await click('Apply proposed edits as tracked changes');
    await click('Download');

    expect(onDownload).toHaveBeenCalledWith('comments', { includeEdits: false });
  });
});
