import { auth } from '@/auth';
import { headers } from 'next/headers';
import { redirect } from 'next/navigation';

async function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();

  if (!session || !session.user) {
    const headersList = await headers();
    const pathname = headersList.get('x-pathname') ?? '/';
    const callbackUrl = encodeURIComponent(pathname);
    redirect(`/api/auth/signin?callbackUrl=${callbackUrl}`);
  }

  return children;
}

export default AuthenticatedLayout;
