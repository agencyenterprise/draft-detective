'use client';

import { useProjectView } from '@/components/results/project-view-context';
import { useExperimentalFeatures } from '@/context/experimental-features-context';
import { PeerReviewTab } from './peer-review/peer-review-tab';

/** Hash format the document explorer understands: `#L5` or `#L5-12`. */
function lineRangeHash(lineRange?: [number, number]): string | undefined {
  if (!lineRange) return undefined;
  const [start, end] = lineRange;
  return start === end ? `#L${start}` : `#L${start}-${end}`;
}

/** The peer review tab as a tab panel, taking its project from the shell. */
export function PeerReviewPanel() {
  const { overview, readOnly, onRevisionChange, onRevisionCreated, navigateToTab } = useProjectView();
  // Peer Review is still alpha: the tab, and the route behind it, exist only
  // for users who opted in.
  const { showExperimentalFeatures, isLoading } = useExperimentalFeatures();

  if (isLoading) return null;

  if (!showExperimentalFeatures) {
    // Reachable from a bookmark or a shared link, since the tab itself is hidden.
    return (
      <div className="flex h-full items-center justify-center p-8">
        <p className="max-w-sm text-center text-sm leading-relaxed text-muted-foreground">
          Peer Review is an alpha feature. Turn on <strong className="font-medium">Alpha features</strong> in your
          profile menu to use it.
        </p>
      </div>
    );
  }

  return (
    <PeerReviewTab
      overview={overview}
      readOnly={readOnly}
      onRevisionChange={onRevisionChange}
      onRevisionCreated={onRevisionCreated}
      onNavigateToDocumentExplorer={(lineRange) => navigateToTab('document-explorer', lineRangeHash(lineRange))}
    />
  );
}
