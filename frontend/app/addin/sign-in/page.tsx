'use client';

import { Button } from '@/components/ui/button';
import { SIGN_IN_PATH, SignInMessage } from '@/lib/addin/sign-in';
import { officeReady } from '@/lib/addin/use-office-init';
import { useQuery } from '@tanstack/react-query';
import { getSession, signIn } from 'next-auth/react';

/**
 * Opened by the task pane as an Office dialog (see `lib/addin/sign-in.ts`).
 *
 * Signed in already, it hands the API token straight back to the pane. Otherwise it
 * offers Microsoft sign-in, which returns here, and then hands it back. Microsoft
 * specifically, because a handoff from Teams is released to the same Microsoft
 * account that asked for it.
 */
/** Whether this page is open as an Office dialog, with a pane to report back to. */
function inOfficeDialog(): boolean {
  return typeof Office !== 'undefined' && typeof Office.context?.ui?.messageParent === 'function';
}

async function handBackSession(): Promise<boolean> {
  await officeReady().catch(() => null);
  if (!inOfficeDialog()) {
    // Opened in a browser tab, not by the add-in: an app sign-in or sign-out that
    // inherited this page as Auth.js's remembered return address. Go to the app.
    window.location.replace('/');
    return true;
  }
  const session = await getSession();
  if (!session?.accessToken || !session.user?.email) return false;
  const message: SignInMessage = { accessToken: session.accessToken, email: session.user.email, via: 'dialog' };
  Office.context.ui.messageParent(JSON.stringify(message));
  return true;
}

export default function AddinSignInPage() {
  const { data: handedBack, isLoading } = useQuery({
    queryKey: ['addin-sign-in'],
    queryFn: handBackSession,
    staleTime: Infinity,
  });

  if (isLoading || handedBack) {
    return <div className="p-4 text-center text-sm text-muted-foreground">Signing in…</div>;
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-3 p-4 text-center">
      <p className="text-sm text-muted-foreground max-w-xs">
        Sign in with the Microsoft account you use in Teams to see what Draft Detective prepared for this document.
      </p>
      {/* Always ask which account: signing in here is how someone switches accounts. */}
      <Button onClick={() => signIn('microsoft-entra-id', { callbackUrl: SIGN_IN_PATH }, { prompt: 'select_account' })}>
        Sign in with Microsoft
      </Button>
    </div>
  );
}
