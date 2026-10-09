import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  openSignInDialog,
  openSignOutDialog,
  SIGN_IN_PATH,
  SIGN_OUT_PATH,
  signInInteractively,
  ssoSignIn,
} from './sign-in';

type Handler = (event: { message?: string; error?: number }) => void;

/** Office's dialog API: `displayDialogAsync` opens a dialog whose events we fire by hand. */
function fakeOffice(opened: 'succeeded' | 'failed' = 'succeeded') {
  const handlers: Record<string, Handler> = {};
  const dialog = {
    close: vi.fn(),
    addEventHandler: (type: string, handler: Handler) => {
      handlers[type] = handler;
    },
  };
  const displayDialogAsync = vi.fn((_url: string, _options: unknown, callback: (result: unknown) => void) =>
    callback(
      opened === 'succeeded'
        ? { status: 'succeeded', value: dialog }
        : { status: 'failed', error: { message: 'blocked by the browser' } },
    ),
  );
  vi.stubGlobal('Office', {
    context: { ui: { displayDialogAsync } },
    AsyncResultStatus: { Succeeded: 'succeeded', Failed: 'failed' },
    EventType: { DialogMessageReceived: 'message', DialogEventReceived: 'event' },
  });
  return { handlers, dialog, displayDialogAsync };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe('openSignInDialog', () => {
  it("opens the sign-in page on the add-in's own origin", async () => {
    const { handlers, displayDialogAsync } = fakeOffice();
    const signedIn = openSignInDialog();
    handlers.message({ message: JSON.stringify({ accessToken: 't', email: 'ana@contoso.com' }) });
    await signedIn;

    expect(displayDialogAsync.mock.calls[0][0]).toBe(`${window.location.origin}${SIGN_IN_PATH}`);
  });

  it('resolves with what the dialog hands back, and closes it', async () => {
    const { handlers, dialog } = fakeOffice();
    const signedIn = openSignInDialog();

    handlers.message({ message: JSON.stringify({ accessToken: 't', email: 'ana@contoso.com' }) });

    await expect(signedIn).resolves.toEqual({ accessToken: 't', email: 'ana@contoso.com' });
    expect(dialog.close).toHaveBeenCalled();
  });

  it('rejects when the person closes the dialog', async () => {
    const { handlers } = fakeOffice();
    const signedIn = openSignInDialog();

    handlers.event({ error: 12006 });

    await expect(signedIn).rejects.toThrow('Sign-in was closed');
  });

  it('rejects when Office cannot open the dialog', async () => {
    fakeOffice('failed');

    await expect(openSignInDialog()).rejects.toThrow('blocked by the browser');
  });
});

function token(payload: Record<string, unknown>): string {
  const body = btoa(JSON.stringify(payload)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return `header.${body}.signature`;
}

/** Office single sign-on: `getAccessToken` answers with `answer`, or fails with it. */
function fakeSso(answer: string | Error) {
  const getAccessToken = vi.fn(() => (answer instanceof Error ? Promise.reject(answer) : Promise.resolve(answer)));
  const { handlers, displayDialogAsync } = fakeOffice();
  const office = (globalThis as unknown as { Office: Record<string, unknown> }).Office;
  office.auth = { getAccessToken };
  return { getAccessToken, handlers, displayDialogAsync };
}

describe('ssoSignIn', () => {
  it('asks Office for a token without prompting, for the silent attempt', async () => {
    const sso = token({ preferred_username: 'ana@contoso.com', oid: 'oid-ana' });
    const { getAccessToken } = fakeSso(sso);

    await expect(ssoSignIn(false)).resolves.toEqual({ accessToken: sso, email: 'ana@contoso.com', via: 'sso' });
    expect(getAccessToken).toHaveBeenCalledWith({
      allowSignInPrompt: false,
      allowConsentPrompt: false,
      forMSGraphAccess: false,
    });
  });

  it('lets Office prompt when the person asked to sign in', async () => {
    const { getAccessToken } = fakeSso(token({ preferred_username: 'ana@contoso.com' }));

    await ssoSignIn(true);

    expect(getAccessToken).toHaveBeenCalledWith(expect.objectContaining({ allowSignInPrompt: true }));
  });
});

describe('signInInteractively', () => {
  it('uses single sign-on when Office can', async () => {
    const sso = token({ preferred_username: 'ana@contoso.com' });
    const { displayDialogAsync } = fakeSso(sso);

    await expect(signInInteractively()).resolves.toMatchObject({ accessToken: sso });
    expect(displayDialogAsync).not.toHaveBeenCalled();
  });

  it('falls back to the dialog when Office cannot', async () => {
    const { handlers, displayDialogAsync } = fakeSso(new Error('13000: single sign-on is not supported'));
    vi.spyOn(console, 'info').mockImplementation(() => undefined);

    const signedIn = signInInteractively();
    await vi.waitFor(() => expect(displayDialogAsync).toHaveBeenCalled());
    handlers.message({ message: JSON.stringify({ accessToken: 'session', email: 'ana@contoso.com' }) });

    await expect(signedIn).resolves.toEqual({ accessToken: 'session', email: 'ana@contoso.com' });
  });
});

describe('openSignOutDialog', () => {
  it('opens the sign-out page and finishes when it reports back', async () => {
    const { handlers, displayDialogAsync, dialog } = fakeOffice();
    const signedOut = openSignOutDialog();

    handlers.message({ message: 'signed-out' });

    await expect(signedOut).resolves.toBeUndefined();
    expect(displayDialogAsync.mock.calls[0][0]).toBe(`${window.location.origin}${SIGN_OUT_PATH}`);
    expect(dialog.close).toHaveBeenCalled();
  });
});
