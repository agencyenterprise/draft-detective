/**
 * Signing the task pane in as a Microsoft account.
 *
 * First choice is Office single sign-on: Office hands over a token for the account
 * already signed in to Word, issued for the add-in's own Entra app (the manifest's
 * `WebApplicationInfo`), so most people never see a sign-in step. When Office cannot
 * (an older build, a manifest without single sign-on, or a tenant that needs consent
 * first), the pane falls back to a dialog: the pane cannot use the app's session
 * cookie, since in Word for the web it runs in a third-party iframe, but a dialog is a
 * top-level window, so Draft Detective's own Microsoft sign-in works there and the
 * dialog page (`/addin/sign-in`) hands the session token back with `messageParent`.
 *
 * Either token names the account by its Entra object id, which is what handoffs from
 * Teams are released to.
 */

export const SIGN_IN_PATH = '/addin/sign-in';
export const SIGN_OUT_PATH = '/addin/sign-out';

/** How the pane got its token: signing out of a dialog session needs the dialog again. */
export type SignInMessage = { accessToken: string; email: string; via: 'sso' | 'dialog' };

function claimsOf(token: string): Record<string, unknown> {
  return JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
}

/**
 * A token from Office single sign-on. With `interactive` false it never shows anything,
 * which is what the pane tries on load; true lets Office prompt to sign in or consent.
 */
export async function ssoSignIn(interactive: boolean): Promise<SignInMessage> {
  const token = await Office.auth.getAccessToken({
    allowSignInPrompt: interactive,
    allowConsentPrompt: interactive,
    forMSGraphAccess: false,
  });
  const claims = claimsOf(token);
  return {
    accessToken: token,
    email: String(claims.preferred_username ?? claims.email ?? 'your Microsoft account'),
    via: 'sso',
  };
}

export async function openSignInDialog(): Promise<SignInMessage> {
  return JSON.parse(await openDialog(SIGN_IN_PATH, 'Sign-in')) as SignInMessage;
}

/**
 * End the Draft Detective session a dialog sign-in left behind. The pane cannot reach
 * that session's cookie, so this opens a dialog that signs out and closes itself.
 */
export async function openSignOutDialog(): Promise<void> {
  await openDialog(SIGN_OUT_PATH, 'Sign-out');
}

/** Open one of the add-in's dialog pages, and resolve with the message it sends back. */
function openDialog(path: string, what: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const url = `${window.location.origin}${path}`;
    Office.context.ui.displayDialogAsync(url, { height: 60, width: 30 }, (opened) => {
      if (opened.status !== Office.AsyncResultStatus.Succeeded) {
        reject(new Error(opened.error.message));
        return;
      }
      const dialog = opened.value;
      dialog.addEventHandler(Office.EventType.DialogMessageReceived, (event) => {
        dialog.close();
        if ('message' in event) {
          resolve(event.message);
        } else {
          reject(new Error(`${what} was interrupted`));
        }
      });
      dialog.addEventHandler(Office.EventType.DialogEventReceived, () => {
        reject(new Error(`${what} was closed`));
      });
    });
  });
}

/** What the sign-in button does: single sign-on with prompts, and the dialog if that fails. */
export async function signInInteractively(): Promise<SignInMessage> {
  try {
    return await ssoSignIn(true);
  } catch (error) {
    console.info('Office single sign-on unavailable, using the sign-in dialog', error);
    return openSignInDialog();
  }
}
