import { useShare } from '@/context/share-context';
import { Query, QueryKey, useQuery } from '@tanstack/react-query';
import {
  getProjectDocumentEndpointApiProjectProjectIdDocumentGet,
  getProjectIssuesEndpointApiProjectProjectIdIssuesGet,
  getProjectOverviewEndpointApiProjectProjectIdOverviewGet,
  getProjectReferencesEndpointApiProjectProjectIdReferencesGet,
  getProjectWorkflowRunsByTypeEndpointApiProjectProjectIdWorkflowRunsGet,
  getWorkflowStateApiWorkflowsWorkflowRunIdGet,
  ProjectOverview,
  WorkflowRunPublic,
  WorkflowRunStatus,
  WorkflowRunSummary,
  WorkflowRunType,
} from '../generated-api';
import { findRunByType } from '../workflow-state';

const REFETCH_INTERVAL_MS = 3000;
// A run waiting on approval can be released from elsewhere (another tab, the
// MCP tool). Poll slowly so the page notices without treating the wait as work.
const AWAITING_APPROVAL_REFETCH_INTERVAL_MS = 15000;

/**
 * Every query of the project page lives under `['project', id]`, so the
 * mutations that invalidate that prefix refresh whichever of them are mounted.
 * The lazy reads carry a version taken from the polled overview, so they
 * refetch only when the overview says their data changed.
 */
export const projectQueryKeys = {
  all: (projectId: string) => ['project', projectId] as const,
  overviews: (projectId: string) => ['project', projectId, 'overview'] as const,
  overview: (projectId: string, revision: number | null | undefined) =>
    ['project', projectId, 'overview', revision ?? 'latest'] as const,
  issues: (projectId: string, revision: number) => ['project', projectId, 'issues', revision] as const,
};

/** Every cached issue list of a project, across revisions. */
export const projectIssuesPrefix = (projectId: string) => ['project', projectId, 'issues'] as const;

/**
 * Keep showing the previous data while a newer version of the same thing
 * loads: the first `prefixLength` parts of the key name the thing (project,
 * revision, run), the rest its version.
 */
function keepWhileSame(key: QueryKey, prefixLength: number) {
  return <T>(previous: T | undefined, previousQuery: Query<T, Error, T, QueryKey> | undefined) => {
    const previousKey = previousQuery?.queryKey;
    if (!previousKey) return undefined;
    const same = key.slice(0, prefixLength).every((part, i) => part === previousKey[i]);
    return same ? previous : undefined;
  };
}

/** What a run's data is a function of: a new run, a new status or a new write to its state. */
function runVersion(run: WorkflowRunPublic | undefined): string {
  if (!run) return 'none';
  return `${run.id}:${run.status}:${run.last_updated_at}`;
}

function runStatusVersion(summary: WorkflowRunSummary | undefined): string {
  return summary ? `${summary.run.id}:${summary.run.status}` : 'none';
}

/**
 * A run's detail while it works changes on every heartbeat, and the views show
 * a spinner rather than its state until it finishes, so only its status counts
 * then. Once it has finished, its last write is what counts.
 */
function runDetailVersion(run: WorkflowRunPublic | undefined): string {
  if (!run) return 'none';
  const active = run.status === WorkflowRunStatus.Running || run.status === WorkflowRunStatus.Pending;
  return active ? `${run.id}:${run.status}` : runVersion(run);
}

/** The project's overview for one revision (null follows the latest), polled while runs are active. */
export function useProjectOverview(projectId: string | null, revision?: number | null) {
  const { shareToken } = useShare();

  return useQuery({
    enabled: !!projectId,
    queryKey: projectQueryKeys.overview(projectId ?? '', revision),
    staleTime: 60 * 1000 * 5,
    queryFn: () =>
      getProjectOverviewEndpointApiProjectProjectIdOverviewGet({
        path: { project_id: projectId! },
        query: { share_token: shareToken, revision: revision ?? undefined },
      }),
    refetchInterval: (query) => {
      const runs = query.state.data?.workflow_runs ?? [];
      if (runs.some((w) => w.run.status === WorkflowRunStatus.Running || w.run.status === WorkflowRunStatus.Pending)) {
        return REFETCH_INTERVAL_MS;
      }
      if (runs.some((w) => w.run.status === WorkflowRunStatus.AwaitingApproval)) {
        return AWAITING_APPROVAL_REFETCH_INTERVAL_MS;
      }
      return false;
    },
  });
}

/** The main document's markdown, title and authors. */
export function useProjectDocument(overview: ProjectOverview) {
  const { shareToken } = useShare();
  const projectId = overview.project.id;
  const runs = overview.workflow_runs ?? [];
  // The markdown lands when processing finishes and the title when summarization does.
  const version = [
    runStatusVersion(findRunByType(runs, WorkflowRunType.DocumentProcessing)),
    runStatusVersion(findRunByType(runs, WorkflowRunType.DocumentSummarization)),
  ].join('|');

  const queryKey = ['project', projectId, 'document', overview.revision, version];

  return useQuery({
    queryKey,
    staleTime: Infinity,
    placeholderData: keepWhileSame(queryKey, 4),
    queryFn: () =>
      getProjectDocumentEndpointApiProjectProjectIdDocumentGet({
        path: { project_id: projectId },
        query: { share_token: shareToken, revision: overview.revision },
      }),
  });
}

/** Every visible issue of the overview's revision. */
export function useProjectIssues(overview: ProjectOverview, { enabled = true }: { enabled?: boolean } = {}) {
  const { shareToken } = useShare();
  const projectId = overview.project.id;

  const queryKey = [...projectQueryKeys.issues(projectId, overview.revision), overview.issues_version];

  return useQuery({
    enabled,
    queryKey,
    staleTime: Infinity,
    placeholderData: keepWhileSame(queryKey, 4),
    queryFn: () =>
      getProjectIssuesEndpointApiProjectProjectIdIssuesGet({
        path: { project_id: projectId },
        query: { share_token: shareToken, revision: overview.revision },
      }),
  });
}

/** Extracted references, their file matches and fetch outcomes. */
export function useProjectReferences(overview: ProjectOverview) {
  const { shareToken } = useShare();
  const projectId = overview.project.id;
  const runs = overview.workflow_runs ?? [];
  const version = [
    WorkflowRunType.ReferenceExtraction,
    WorkflowRunType.ReferenceFileMatching,
    WorkflowRunType.ReferenceDownloader,
  ]
    .map((type) => runVersion(findRunByType(runs, type)?.run))
    .join('|');

  const queryKey = ['project', projectId, 'references', overview.revision, version];

  return useQuery({
    queryKey,
    staleTime: Infinity,
    placeholderData: keepWhileSame(queryKey, 4),
    queryFn: () =>
      getProjectReferencesEndpointApiProjectProjectIdReferencesGet({
        path: { project_id: projectId },
        query: { share_token: shareToken, revision: overview.revision },
      }),
  });
}

/** One run with its state and cost. */
export function useWorkflowRunDetail(projectId: string, summary: WorkflowRunSummary | undefined) {
  const { shareToken } = useShare();
  const runId = summary?.run.id;

  const queryKey = ['project', projectId, 'run', runId, runDetailVersion(summary?.run)];

  return useQuery({
    enabled: !!runId,
    queryKey,
    staleTime: Infinity,
    placeholderData: keepWhileSame(queryKey, 4),
    queryFn: () =>
      getWorkflowStateApiWorkflowsWorkflowRunIdGet({
        path: { workflow_run_id: runId! },
        query: { share_token: shareToken },
      }),
  });
}

/** Every run of one assessment on the overview's revision, newest first. */
export function useWorkflowRunHistory(overview: ProjectOverview, workflowType: WorkflowRunType | null) {
  const { shareToken } = useShare();
  const projectId = overview.project.id;
  // A new run, or one finishing, is what adds to or changes the history.
  const latest = workflowType ? findRunByType(overview.workflow_runs ?? [], workflowType) : undefined;

  const queryKey = ['project', projectId, 'run-history', workflowType, overview.revision, runStatusVersion(latest)];

  return useQuery({
    enabled: !!workflowType,
    queryKey,
    staleTime: Infinity,
    placeholderData: keepWhileSame(queryKey, 5),
    queryFn: () =>
      getProjectWorkflowRunsByTypeEndpointApiProjectProjectIdWorkflowRunsGet({
        path: { project_id: projectId },
        query: { workflow_type: workflowType!, revision: overview.revision, share_token: shareToken },
      }),
  });
}
