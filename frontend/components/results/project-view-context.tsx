'use client';

import { ProjectOverview, WorkflowRunType } from '@/lib/generated-api';
import { createContext, useContext } from 'react';
import { TabType } from './constants';

export interface ProjectViewContextValue {
  /** The project, its runs' statuses and its files; tabs fetch anything heavier themselves. */
  overview: ProjectOverview;
  /** When true, hides edit/action controls (for shared view) */
  readOnly: boolean;
  /** Currently displayed revision */
  selectedRevision?: number;
  /** Callback when user switches revision */
  onRevisionChange?: (revision: number) => void;
  /** Callback after a new revision is created, to follow it in the view */
  onRevisionCreated?: () => void;
  /** Switch to another tab, optionally landing on a URL hash (e.g. `#L5-12`) */
  navigateToTab: (tab: TabType, hash?: string) => void;
  /** Route for an assessment on the assessments tab, or one run of it. */
  assessmentHref: (workflowType: WorkflowRunType, runId?: string | null) => string;
}

const ProjectViewContext = createContext<ProjectViewContextValue | undefined>(undefined);

export const ProjectViewProvider = ProjectViewContext.Provider;

export function useProjectView() {
  const context = useContext(ProjectViewContext);
  if (!context) {
    throw new Error('useProjectView must be used within a ProjectShell');
  }
  return context;
}
