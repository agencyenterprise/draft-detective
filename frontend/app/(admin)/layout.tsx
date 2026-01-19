import { auth } from '@/auth';
import { UserRole } from '@/lib/generated-api';
import { redirect } from 'next/navigation';

async function AdminLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();

  if (!session || !session.user) {
    redirect('/api/auth/signin');
  }

  if (session.user.role !== UserRole.Admin) {
    redirect('/');
  }

  return children;
}

export default AdminLayout;
