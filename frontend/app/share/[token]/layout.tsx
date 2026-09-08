'use client';

import { ProjectShell } from '@/components/results/project-shell';
import { ShellStatusScreen } from '@/components/results/shell-status-screen';
import { useTabRouting } from '@/components/results/use-tab-routing';
import { OwnerSharedBanner } from '@/components/share/owner-shared-banner';
import { ShareProvider } from '@/context/share-context';
import { getSharedResourceApiPublicShareTokenGet } from '@/lib/generated-api';
import { useUserMe } from '@/lib/hooks/use-user-me';
import { useQuery } from '@tanstack/react-query';
import { Link2Off } from 'lucide-react';
import { useParams } from 'next/navigation';
import { ReactNode } from 'react';

export default function SharedProjectLayout({ children }: { children: ReactNode }) {
  const params = useParams();
  const token = params.token as string;

  const basePath = `/share/${token}`;
  const { activeTab, onTabChange } = useTabRouting(basePath);
  const { data: currentUser } = useUserMe();

  const { data, isLoading, error } = useQuery({
    queryKey: ['sharedProject', token],
    queryFn: () => getSharedResourceApiPublicShareTokenGet({ path: { token } }),
    retry: false,
  });

  // Whether the signed-in visitor is the owner of the project behind this link.
  const isOwner = !!currentUser?.id && !!data?.project?.user_id && currentUser.id === data.project.user_id;

  if (isLoading) {
    return (
      <ShellStatusScreen>
        <div className="border-primary mx-auto mb-4 size-8 animate-spin rounded-full border-b-2" />
        <p className="text-muted-foreground">Loading shared project...</p>
      </ShellStatusScreen>
    );
  }

  if (error || !data) {
    return (
      <ShellStatusScreen>
        <Link2Off className="mx-auto mb-4 size-10 text-muted-foreground" />
        <h1 className="mb-2 text-lg font-semibold">Link not found</h1>
        <p className="text-sm text-muted-foreground">This share link may have expired or been disabled by the owner.</p>
      </ShellStatusScreen>
    );
  }

  return (
    <ShareProvider token={token}>
      <ProjectShell
        projectDetail={data}
        basePath={basePath}
        readOnly
        activeTab={activeTab}
        onTabChange={onTabChange}
        notice={isOwner ? <OwnerSharedBanner projectId={data.project.id} /> : undefined}
      >
        {children}
      </ProjectShell>
    </ShareProvider>
  );
}
