'use client';

import { officeReady } from '@/lib/addin/use-office-init';
import { useQuery } from '@tanstack/react-query';
import { signOut } from 'next-auth/react';

/**
 * Opened by the task pane as an Office dialog (see `openSignOutDialog` in
 * `lib/addin/sign-in.ts`): ends the Draft Detective session a dialog sign-in left
 * behind, which the pane itself cannot reach, then tells the pane and closes.
 */
async function endSession(): Promise<boolean> {
  await officeReady();
  await signOut({ redirect: false });
  Office.context.ui.messageParent('signed-out');
  return true;
}

export default function AddinSignOutPage() {
  useQuery({ queryKey: ['addin-sign-out'], queryFn: endSession, staleTime: Infinity, retry: false });
  return <div className="p-4 text-center text-sm text-muted-foreground">Signing out…</div>;
}
