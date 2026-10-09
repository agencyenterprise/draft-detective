import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { ApiError } from '@/lib/api-error';
import {
  dismissApiMicrosoftWordHandoffsHandoffIdDismissedPost,
  listPendingApiMicrosoftWordHandoffsGet,
  reportAppliedApiMicrosoftWordHandoffsHandoffIdAppliedPost,
  type HandoffView,
  type PendingHandoffs,
} from '@/lib/generated-api';
import { applyHandoff } from '@/lib/addin/apply-handoff';
import { openSignOutDialog, signInInteractively, ssoSignIn } from '@/lib/addin/sign-in';
import { flush, renderInto, Rendered, testQueryClient, withQueryClient } from '@/lib/test-render';
import { HandoffPanel } from './handoff-panel';

vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  listPendingApiMicrosoftWordHandoffsGet: vi.fn(),
  reportAppliedApiMicrosoftWordHandoffsHandoffIdAppliedPost: vi.fn(),
  dismissApiMicrosoftWordHandoffsHandoffIdDismissedPost: vi.fn(),
}));
vi.mock('@/lib/addin/apply-handoff', () => ({ applyHandoff: vi.fn() }));
vi.mock('@/lib/addin/sign-in', () => ({
  ssoSignIn: vi.fn(),
  signInInteractively: vi.fn(),
  openSignOutDialog: vi.fn(),
}));

const list = vi.mocked(listPendingApiMicrosoftWordHandoffsGet);
const report = vi.mocked(reportAppliedApiMicrosoftWordHandoffsHandoffIdAppliedPost);
const dismiss = vi.mocked(dismissApiMicrosoftWordHandoffsHandoffIdDismissedPost);
const apply = vi.mocked(applyHandoff);
const interactive = vi.mocked(signInInteractively);
const silent = vi.mocked(ssoSignIn);
const signOutDialog = vi.mocked(openSignOutDialog);

const DOCUMENT_URL = 'https://contoso.sharepoint.com/sites/Policy/Shared Documents/Draft.docx';
const SIGNED_IN = { accessToken: 'tok', email: 'ana@contoso.com', via: 'sso' as const };
const DIALOG_SIGNED_IN = { ...SIGNED_IN, via: 'dialog' as const };

const handoff = (id: string, name = 'Draft.docx'): HandoffView => ({
  id,
  document_name: name,
  document_url: `https://contoso.sharepoint.com/${name}`,
  items: { comments: [{ quote: 'the only option', comment: 'Overclaims.' }], edits: [] },
  created_at: new Date('2026-10-09T12:00:00Z'),
});

let rendered: Rendered | null = null;

async function render(): Promise<HTMLElement> {
  rendered = await renderInto(withQueryClient(testQueryClient(), <HandoffPanel />));
  // Signing in silently, then listing: two rounds of promises before anything shows.
  await flush();
  await flush();
  return rendered.container;
}

function button(container: HTMLElement, label: string): HTMLButtonElement {
  const found = [...container.querySelectorAll('button')].find((b) => b.textContent?.includes(label));
  if (!found) throw new Error(`no "${label}" button in: ${container.textContent}`);
  return found;
}

async function click(container: HTMLElement, label: string): Promise<void> {
  await act(async () => button(container, label).click());
  await flush();
}

beforeEach(() => {
  vi.stubGlobal('Office', { context: { document: { url: DOCUMENT_URL } } });
  // By default Office cannot sign anyone in silently, so the pane offers the button.
  silent.mockRejectedValue(new Error('13001: not signed in'));
  interactive.mockResolvedValue(DIALOG_SIGNED_IN);
  list.mockResolvedValue({ here: [], elsewhere: [] } as PendingHandoffs);
  report.mockResolvedValue(undefined as never);
  dismiss.mockResolvedValue(undefined as never);
});

afterEach(async () => {
  await rendered?.unmount();
  rendered = null;
  vi.unstubAllGlobals();
  vi.resetAllMocks();
});

describe('HandoffPanel', () => {
  it('asks nothing of the API until someone has signed in', async () => {
    const container = await render();

    expect(container.textContent).toContain('Sign in with Microsoft');
    expect(list).not.toHaveBeenCalled();
  });

  it('after signing in, asks for this document as that person', async () => {
    const container = await render();
    await click(container, 'Sign in with Microsoft');

    expect(list).toHaveBeenCalledWith({
      query: { url: DOCUMENT_URL },
      headers: { Authorization: 'Bearer tok' },
    });
    expect(container.textContent).toContain('Nothing waiting from Teams for ana@contoso.com');
  });

  it('single sign-on signs them in without a click', async () => {
    silent.mockResolvedValue(SIGNED_IN);
    await render();

    expect(silent).toHaveBeenCalledWith(false);
    expect(interactive).not.toHaveBeenCalled();
    expect(list).toHaveBeenCalledWith(expect.objectContaining({ headers: { Authorization: 'Bearer tok' } }));
  });

  it('a failed sign-in says why and stays signed out', async () => {
    interactive.mockRejectedValue(new Error('Sign-in was closed'));
    const container = await render();
    await click(container, 'Sign in with Microsoft');

    expect(container.textContent).toContain('Sign-in was closed');
    expect(list).not.toHaveBeenCalled();
  });

  it('a refused token sends them back to sign in, without retrying silently', async () => {
    silent.mockResolvedValue(SIGNED_IN);
    list.mockRejectedValue(new ApiError(401));
    const container = await render();
    const asked = silent.mock.calls.length;
    await flush();

    expect(container.textContent).toContain('Your sign-in expired');
    expect(list).toHaveBeenCalledTimes(1);
    expect(silent).toHaveBeenCalledTimes(asked);
  });

  it('a single sign-on token is renewed before each call, so it never expires under the pane', async () => {
    silent.mockResolvedValueOnce(SIGNED_IN).mockResolvedValue({ ...SIGNED_IN, accessToken: 'renewed' });
    await render();

    expect(list).toHaveBeenCalledWith(expect.objectContaining({ headers: { Authorization: 'Bearer renewed' } }));
  });

  it('when Office will not renew the token, they are asked to sign in again', async () => {
    silent.mockResolvedValueOnce(SIGNED_IN).mockRejectedValue(new Error('13001'));
    const container = await render();

    expect(list).not.toHaveBeenCalled();
    expect(container.textContent).toContain('Your sign-in expired');
  });

  it('signing in again after a refusal asks again', async () => {
    silent.mockResolvedValue(SIGNED_IN);
    list.mockRejectedValueOnce(new ApiError(401));
    const container = await render();

    await click(container, 'Sign in with Microsoft');

    expect(interactive).toHaveBeenCalled();
    expect(container.textContent).toContain('Nothing waiting from Teams');
  });

  it('signing out of single sign-on stops it signing them straight back in', async () => {
    silent.mockResolvedValue(SIGNED_IN);
    const container = await render();
    expect(container.textContent).toContain('Signed in as ana@contoso.com');

    const asked = silent.mock.calls.length;
    await click(container, 'Sign out');

    expect(container.textContent).toContain('Sign in with Microsoft');
    expect(silent).toHaveBeenCalledTimes(asked);
    expect(signOutDialog).not.toHaveBeenCalled();
  });

  it('signing out of a dialog sign-in ends that session too', async () => {
    interactive.mockResolvedValue(DIALOG_SIGNED_IN);
    signOutDialog.mockResolvedValue(undefined);
    const container = await render();
    await click(container, 'Sign in with Microsoft');

    await click(container, 'Sign out');

    expect(signOutDialog).toHaveBeenCalled();
    expect(container.textContent).toContain('Sign in with Microsoft');
  });

  it('a sign-out dialog that is closed early still signs the pane out', async () => {
    interactive.mockResolvedValue(DIALOG_SIGNED_IN);
    signOutDialog.mockRejectedValue(new Error('Sign-out was closed'));
    const container = await render();
    await click(container, 'Sign in with Microsoft');

    await click(container, 'Sign out');

    expect(container.textContent).toContain('Sign in with Microsoft');
  });

  it('Apply writes the handoff, then reports what landed', async () => {
    silent.mockResolvedValue(SIGNED_IN);
    const pending = handoff('h1');
    list.mockResolvedValue({ here: [pending], elsewhere: [] });
    const outcome = {
      items: [
        { kind: 'comment' as const, quote: 'the only option', applied: true, detail: '' },
        { kind: 'edit' as const, quote: 'recieve', applied: false, detail: 'the words are no longer in the document' },
      ],
    };
    apply.mockResolvedValue(outcome);
    const container = await render();

    await click(container, 'Apply');

    expect(apply).toHaveBeenCalledWith(pending, 'Bearer tok');
    expect(report).toHaveBeenCalledWith({
      path: { handoff_id: 'h1' },
      body: { outcome },
      headers: { Authorization: 'Bearer tok' },
    });
    expect(container.textContent).toContain('Applied 1 of 2');
    expect(container.textContent).toContain('the words are no longer in the document');
  });

  it('a failed write is shown, and nothing is reported to Teams', async () => {
    silent.mockResolvedValue(SIGNED_IN);
    list.mockResolvedValue({ here: [handoff('h1')], elsewhere: [] });
    apply.mockRejectedValue(new Error('Word refused the change'));
    const container = await render();

    await click(container, 'Apply');

    expect(report).not.toHaveBeenCalled();
    expect(container.textContent).toContain('Word refused the change');
  });

  it('Dismiss closes the handoff and checks again', async () => {
    silent.mockResolvedValue(SIGNED_IN);
    list.mockResolvedValueOnce({ here: [handoff('h1')], elsewhere: [] });
    const container = await render();

    await click(container, 'Dismiss');

    expect(dismiss).toHaveBeenCalledWith({ path: { handoff_id: 'h1' }, headers: { Authorization: 'Bearer tok' } });
    expect(apply).not.toHaveBeenCalled();
    expect(list).toHaveBeenCalledTimes(2);
  });

  it('suggestions for another document are pointed at, not offered here', async () => {
    silent.mockResolvedValue(SIGNED_IN);
    list.mockResolvedValue({ here: [], elsewhere: [handoff('h2', 'Other.docx')] });
    const container = await render();

    expect(container.textContent).toContain('Other.docx');
    expect(() => button(container, 'Apply')).toThrow();
  });
});
