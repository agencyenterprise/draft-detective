import { auth } from '@/auth';
import { baseUrl } from '@/lib/api';
import { getCurrentUserInfoApiUsersMeGet, UserRole } from '@/lib/generated-api';
import { redirect } from 'next/navigation';

async function AdminLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();

  if (!session || !session.user || !session.accessToken) {
    redirect('/api/auth/signin');
  }

  const user = await getCurrentUserInfoApiUsersMeGet({ baseUrl, auth: session.accessToken });

  if (!user || user.role !== UserRole.Admin) {
    redirect('/');
  }

  return children;
}

export default AdminLayout;
