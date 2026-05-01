'use client';

import { OwnerSharedBanner } from '@/components/share/owner-shared-banner';
import { ResultsVisualization } from '@/components/results/results-visualization';
import { ShareProvider } from '@/context/share-context';
import { getSharedResourceApiPublicShareTokenGet } from '@/lib/generated-api';
import { useUserMe } from '@/lib/hooks/use-user-me';
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'next/navigation';

export default function SharedProjectPage() {
  const params = useParams();
  const token = params.token as string;

  const { data: currentUser } = useUserMe();

  const { data, isLoading, error } = useQuery({
    queryKey: ['sharedProject', token],
    queryFn: () => getSharedResourceApiPublicShareTokenGet({ path: { token } }),
    retry: false,
  });

  // Check if the current authenticated user is the owner of this project
  const isOwner = currentUser?.id && data?.project?.user_id && currentUser.id === data.project.user_id;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading shared assessment...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center max-w-md mx-auto p-6">
          <div className="text-6xl mb-4">🔗</div>
          <h1 className="text-2xl font-bold text-foreground mb-2">Link Not Found</h1>
          <p className="text-muted-foreground">This share link may have expired or been disabled by the owner.</p>
        </div>
      </div>
    );
  }

  return (
    <ShareProvider token={token}>
      {isOwner && <OwnerSharedBanner projectId={data.project.id} />}
      <ResultsVisualization projectDetail={data} readOnly />
    </ShareProvider>
  );
}
