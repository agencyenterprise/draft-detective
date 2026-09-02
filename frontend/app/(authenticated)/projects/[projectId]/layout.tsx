'use client';

import { ProjectShell } from '@/components/results/project-shell';
import { ShellStatusScreen } from '@/components/results/shell-status-screen';
import { useProjectShellState } from '@/components/results/use-project-shell-state';
import { useTabRouting } from '@/components/results/use-tab-routing';
import { isApiError } from '@/lib/api-error';
import { needsReferenceReview } from '@/components/workflows/utils';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { FileXIcon, LockIcon } from 'lucide-react';
import { useParams } from 'next/navigation';
import { ReactNode } from 'react';

/** One route per tab under `/projects/<id>`; the document explorer is the root. */
export default function ProjectLayout({ children }: { children: ReactNode }) {
  const params = useParams();
  const projectId = params.projectId as string;

  const { activeTab, onTabChange } = useTabRouting(`/projects/${projectId}`);

  const {
    project,
    workflowDetails,
    isLoading,
    error,
    effectiveRevision,
    handleRevisionChange,
    handleRevisionCreated,
    handleTitleSave,
    isTitleSaving,
    readOnly,
    isReadOnly,
    isViewingOldRevision,
  } = useProjectShellState(projectId);
  const { workflowTypes } = useWorkflowTypes();

  if (isLoading) {
    return (
      <ShellStatusScreen>
        <div className="border-primary mx-auto mb-4 size-8 animate-spin rounded-full border-b-2" />
        <p className="text-muted-foreground">Loading project...</p>
      </ShellStatusScreen>
    );
  }

  if (isApiError(error, 403)) {
    return (
      <ShellStatusScreen>
        <LockIcon className="mx-auto mb-4 size-10 text-muted-foreground" />
        <h2 className="mb-2 text-lg font-semibold">Access denied</h2>
        <p className="text-sm text-muted-foreground">
          You don&apos;t have permission to view this project. Contact the project owner to request access.
        </p>
      </ShellStatusScreen>
    );
  }

  if (isApiError(error, 404)) {
    return (
      <ShellStatusScreen>
        <FileXIcon className="mx-auto mb-4 size-10 text-muted-foreground" />
        <h2 className="mb-2 text-lg font-semibold">Project not found</h2>
        <p className="text-sm text-muted-foreground">This project doesn&apos;t exist or may have been deleted.</p>
      </ShellStatusScreen>
    );
  }

  if (error) {
    return (
      <ShellStatusScreen>
        <p className="text-destructive">{error.message}</p>
      </ShellStatusScreen>
    );
  }

  if (!project) {
    return (
      <ShellStatusScreen>
        <p className="text-muted-foreground">Nothing to show.</p>
      </ShellStatusScreen>
    );
  }

  return (
    <ProjectShell
      projectDetail={project}
      activeTab={activeTab}
      onTabChange={onTabChange}
      readOnly={readOnly}
      onTitleSave={isReadOnly ? undefined : handleTitleSave}
      isTitleSaving={isReadOnly ? undefined : isTitleSaving}
      needsReferenceReview={
        !isReadOnly && !isViewingOldRevision && needsReferenceReview(workflowDetails, workflowTypes)
      }
      selectedRevision={effectiveRevision}
      onRevisionChange={handleRevisionChange}
      onRevisionCreated={handleRevisionCreated}
    >
      {children}
    </ProjectShell>
  );
}
