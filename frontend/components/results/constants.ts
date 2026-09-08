import { WorkflowRunType } from '@/lib/generated-api';

export const TABS = ['document-explorer', 'references', 'files', 'analyses', 'peer-review'] as const;

export type TabType = (typeof TABS)[number];

/** The tab shown at a base route, which therefore has no path segment of its own. */
export const ROOT_TAB: TabType = 'document-explorer';

/**
 * Route for a tab under a base path (`/projects/[projectId]` or `/share/[token]`).
 * The root tab lives at the base path itself.
 */
export function tabHref(basePath: string, tab: TabType): string {
  return tab === ROOT_TAB ? basePath : `${basePath}/${tab}`;
}

/**
 * Resolve the active tab from a pathname under `basePath`. Only the first
 * segment names the tab; anything after it belongs to the tab, like the
 * assessment at `/analyses/results_extraction`.
 */
export function tabFromPathname(pathname: string, basePath: string): TabType {
  const [first = ''] = pathname.slice(basePath.length).replace(/^\//, '').split('/');
  return TABS.find((tab) => tab === first) ?? ROOT_TAB;
}

/**
 * Route for one assessment on the assessments tab, optionally a particular run
 * of it (`?run=`), so an issue elsewhere can point at the report it came from.
 */
export function assessmentHref(basePath: string, workflowType: WorkflowRunType, runId?: string | null): string {
  const base = `${tabHref(basePath, 'analyses')}/${workflowType}`;
  return runId ? `${base}?run=${encodeURIComponent(runId)}` : base;
}

const WORKFLOW_RUN_TYPES: ReadonlySet<string> = new Set(Object.values(WorkflowRunType));

/** The route segment as a workflow type, or null for anything else (an old or mistyped URL). */
export function parseWorkflowRunType(segment: string | string[] | undefined): WorkflowRunType | null {
  return typeof segment === 'string' && WORKFLOW_RUN_TYPES.has(segment) ? (segment as WorkflowRunType) : null;
}
