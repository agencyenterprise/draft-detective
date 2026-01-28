import * as React from 'react';
import { Loader2 } from 'lucide-react';
import { EmptyState } from '@/components/shared';
import { SkeletonList, SkeletonParagraphs } from '@/components/ui/skeleton-list';

interface TabWithLoadingStatesProps<T> {
  title: string;
  data: T | null | undefined;
  isProcessing: boolean;
  hasData: (data: T | undefined | null) => boolean;
  loadingMessage: { title: string; description: string };
  emptyMessage: { icon: React.ReactNode; title: string; description?: string };
  emptyStateChildren?: React.ReactNode;
  skeletonType?: 'list' | 'paragraphs';
  skeletonCount?: number;
  triggerButton?: React.ReactNode;
  children: (data: T) => React.ReactNode;
}

/**
 * Higher-order component that provides consistent loading and empty states for tab content.
 * Handles three states:
 * 1. Loading: Shows spinner, message, and skeleton placeholders
 * 2. Empty: Shows icon and explanation message
 * 3. Data: Renders children with actual data
 */
export function TabWithLoadingStates<T>({
  title,
  data,
  isProcessing,
  hasData,
  loadingMessage,
  emptyMessage,
  emptyStateChildren,
  skeletonType = 'list',
  skeletonCount = 3,
  triggerButton,
  children,
}: TabWithLoadingStatesProps<T>) {
  const isLoading = !hasData(data) && isProcessing;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold">{title}</h3>
        {triggerButton}
      </div>

      {isLoading && (
        <EmptyState
          icon={<Loader2 className="h-12 w-12 animate-spin text-primary" />}
          title={loadingMessage.title}
          description={loadingMessage.description}
        >
          {skeletonType === 'list' ? (
            <SkeletonList count={skeletonCount} />
          ) : (
            <SkeletonParagraphs count={skeletonCount} />
          )}
        </EmptyState>
      )}

      {!isLoading && !hasData(data) && <EmptyState {...emptyMessage}>{emptyStateChildren}</EmptyState>}

      {!isLoading && hasData(data) && children(data!)}
    </div>
  );
}
