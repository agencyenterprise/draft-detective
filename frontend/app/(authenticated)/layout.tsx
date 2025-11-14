import { auth } from '@/auth';
import { redirect } from 'next/navigation';
import { headers } from 'next/headers';
import { ApplicationShell } from '@/components/application-shell';

async function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();

  if (!session) {
    const headersList = await headers();
    const pathname = headersList.get('x-pathname') ?? '/';
    const callbackUrl = encodeURIComponent(pathname);
    redirect(`/api/auth/signin?callbackUrl=${callbackUrl}`);
  }

  return <ApplicationShell user={session.user}>{children}</ApplicationShell>;
}

export default AuthenticatedLayout;
