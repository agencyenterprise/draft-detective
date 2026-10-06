'use client';

import { useProjectView } from '@/components/results/project-view-context';
import { FilesTab } from './files/files-tab';

/** The files tab as a tab panel, taking its project from the shell. */
export function FilesPanel() {
  const { overview, readOnly, onRevisionCreated } = useProjectView();

  return <FilesTab overview={overview} readOnly={readOnly} onRevisionCreated={onRevisionCreated} />;
}
