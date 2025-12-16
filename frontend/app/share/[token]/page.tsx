'use client';

import { TabType } from '@/components/wizard/results-step/constants';
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

  const [activeTab, setActiveTab] = useState<TabType>('document-explorer');
  const [viewMode, setViewMode] = useState<DocRenderMode>('markdown');

  const { data, isLoading, error } = useQuery({
    queryKey: ['sharedProject', token],
    queryFn: () => getSharedResourceApiPublicShareTokenGet({ path: { token } }),
    retry: false,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading shared analysis...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
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
      <div className="min-h-screen bg-gray-50">
        <div className="bg-white border-b shadow-sm">
          <div className="max-w-7xl mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-xl font-bold text-gray-900">{data.project.title}</h1>
                <p className="text-sm text-muted-foreground">Shared analysis • Read-only view</p>
              </div>
              <div className="text-xs text-muted-foreground bg-gray-100 px-3 py-1 rounded-full">AI Reviewer</div>
            </div>
          </div>
        </div>

        <div className="max-w-7xl mx-auto px-4 py-6">
          <ResultsVisualization
            projectDetail={data}
            isProcessing={false}
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            activeTab={activeTab}
            onTabChange={setActiveTab}
            readOnly
          />
        </div>
      </div>
    </ShareProvider>
  );
}
