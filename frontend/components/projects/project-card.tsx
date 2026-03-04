import { DeleteProjectDialog } from '@/components/delete-project-dialog';
import { Button } from '@/components/ui/button';
import { StatusIndicator } from '@/components/ui/status-indicator';
import { ProjectListItem, WorkflowRun, WorkflowRunType } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { formatDistanceToNow } from 'date-fns';
import { ChevronRightIcon } from 'lucide-react';
import Link from 'next/link';
import { useMemo } from 'react';

interface ProjectCardProps {
  item: ProjectListItem;
}

interface WorkflowTypeSummary {
  type: WorkflowRunType;
  count: number;
  latestRun: WorkflowRun;
}

/**
 * Groups workflow runs by type and returns summary with count and latest run.
 * Latest run is determined by most recent created_at timestamp.
 */
function groupWorkflowsByType(runs: WorkflowRun[]): WorkflowTypeSummary[] {
  const grouped = runs.reduce(
    (acc, run) => {
      if (!acc[run.type]) {
        acc[run.type] = [];
      }
      acc[run.type].push(run);
      return acc;
    },
    {} as Record<WorkflowRunType, WorkflowRun[]>,
  );

  return Object.entries(grouped).map(([type, typeRuns]) => {
    const sortedRuns = [...typeRuns].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
    return {
      type: type as WorkflowRunType,
      count: typeRuns.length,
      latestRun: sortedRuns[0],
    };
  });
}

export function ProjectCard({ item }: ProjectCardProps) {
  const { project, workflow_runs } = item;
  const { isWorkflowTypeVisible, getWorkflowTypeName } = useWorkflowTypes();

  const displayWorkflows = useMemo(
    () => workflow_runs?.filter((w) => isWorkflowTypeVisible(w.type)) || [],
    [workflow_runs, isWorkflowTypeVisible],
  );

  const workflowSummaries = useMemo(() => groupWorkflowsByType(displayWorkflows), [displayWorkflows]);

  return (
    <div className="flex items-center justify-between p-4 border rounded-lg transition-colors hover:bg-muted/50">
      <div className="flex-1 min-w-0">
        <h3 className="font-medium truncate mb-1">{project.title}</h3>

        <div className="flex flex-col mb-1 min-w-0">
          {workflowSummaries.map((summary) => (
            <p key={summary.type} className="text-sm pl-2">
              {getWorkflowTypeName(summary.type)}
              {summary.count > 1 && <span className="text-muted-foreground ml-1">({summary.count} runs)</span>}
              : <StatusIndicator status={summary.latestRun.status} />
            </p>
          ))}
        </div>

        <p className="text-sm text-muted-foreground mt-1">
          Created {formatDistanceToNow(project.created_at, { addSuffix: true })}
        </p>
      </div>

      <div className="flex gap-2">
        <Link href={`/projects/${project.id}`}>
          <Button variant="outline" size="sm">
            View Project <ChevronRightIcon className="w-4 h-4" />
          </Button>
        </Link>

        <DeleteProjectDialog projectId={project.id} projectTitle={project.title} />
      </div>
    </div>
  );
}
