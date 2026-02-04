'use client';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ArrowRight, Eye, X } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

interface OwnerSharedBannerProps {
  projectId: string;
}

/**
 * Banner shown to project owners when they visit their own shared link.
 * Helps them understand they're viewing the public version and provides
 * quick access to the full editor view.
 */
export function OwnerSharedBanner({ projectId }: OwnerSharedBannerProps) {
  const [isDismissed, setIsDismissed] = useState(false);

  if (isDismissed) {
    return null;
  }

  return (
    <div
      className={cn(
        'sticky top-0 z-50 w-full',
        'mb-4',
        'bg-blue-50 border-b border-blue-200',
        'dark:bg-blue-950/50 dark:border-blue-800/50',
      )}
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between py-3 gap-6">
          <div className="flex items-center gap-3 min-w-0">
            <div
              className={cn(
                'flex items-center justify-center shrink-0',
                'h-8 w-8 rounded-full',
                'bg-blue-100 dark:bg-blue-900/50',
              )}
            >
              <Eye className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            </div>
            <p className="text-sm text-blue-900 dark:text-blue-100">
              <span className="font-medium">You&apos;re viewing the shared version</span>
              <span className="hidden sm:inline text-blue-700 dark:text-blue-300"> of your project</span>
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <Button asChild size="sm" className="bg-blue-600 hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-500">
              <Link href={`/projects/${projectId}`}>
                Edit Project
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className={cn(
                'h-8 w-8',
                'text-blue-600 hover:text-blue-800 hover:bg-blue-100',
                'dark:text-blue-400 dark:hover:text-blue-200 dark:hover:bg-blue-900/50',
              )}
              onClick={() => setIsDismissed(true)}
              aria-label="Dismiss banner"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
