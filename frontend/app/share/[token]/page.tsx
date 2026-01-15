'use client';

import { ResultsVisualization } from '@/components/wizard/results-step/results-visualization';
import { ShareProvider } from '@/context/share-context';
import { DocRenderMode } from '@/lib/constants';
import { getSharedResourceApiPublicShareTokenGet } from '@/lib/generated-api';
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import { useState } from 'react';

export default function SharedProjectPage() {
  const params = useParams();
  const token = params.token as string;

  const [viewMode, setViewMode] = useState<DocRenderMode>('markdown');

  const { data, isLoading, error } = useQuery({
    queryKey: ['sharedProject', token],
    queryFn: () => getSharedResourceApiPublicShareTokenGet({ path: { token } }),
    retry: false,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading shared analysis...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center max-w-md mx-auto p-6">
          <div className="text-6xl mb-4">🔗</div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Link Not Found</h1>
          <p className="text-muted-foreground">This share link may have expired or been disabled by the owner.</p>
        </div>
      </div>
    );
  }

  return (
    <ShareProvider token={token}>
      <ResultsVisualization projectDetail={data} viewMode={viewMode} onViewModeChange={setViewMode} readOnly />
    </ShareProvider>
  );
}
