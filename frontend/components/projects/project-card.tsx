import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { StatusIndicator } from '@/components/ui/status-indicator';
import { DeleteProjectDialog } from '@/components/delete-project-dialog';
import { getToolMetadata, ToolDefinition } from '@/lib/tool-registry';
import { getWorkflowTypeName } from '@/lib/workflow-state';
import { ProjectListItem } from '@/lib/generated-api';
import { formatDistanceToNow } from 'date-fns';
import { ChevronRightIcon } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';

type ProjectWithToolInfo = ProjectListItem & {
  toolInfo: ToolDefinition | null;
};

interface ProjectCardProps {
  item: ProjectWithToolInfo;
}

export function ProjectCard({ item }: ProjectCardProps) {
  const { project, workflow_runs, toolInfo } = item;
  const isToolRun = toolInfo !== null;

  const { isWorkflowTypeVisible } = useWorkflowTypes();
  const toolMetadata = toolInfo ? getToolMetadata(toolInfo.name) : null;
  const ToolIcon = toolMetadata?.icon;

  // For regular projects, filter to only show user-visible workflows
  // Internal workflows are filtered out using the centralized registry
  const displayWorkflows = isToolRun
    ? workflow_runs || []
    : workflow_runs?.filter((w) => isWorkflowTypeVisible(w.type)) || [];

  return (
    <div
      className={cn(
        'flex items-center justify-between p-4 border rounded-lg transition-colors',
        isToolRun ? 'bg-blue-50/50 hover:bg-blue-50 border-blue-200' : 'hover:bg-muted/50',
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          {isToolRun && ToolIcon && <ToolIcon className="h-4 w-4 text-blue-600 shrink-0" />}
          <h3 className="font-medium truncate">{project.title}</h3>
          {isToolRun && (
            <Badge variant="outline" className="text-xs">
              {toolInfo.name}
            </Badge>
          )}
        </div>

        {isToolRun ? (
          <p className="text-sm text-muted-foreground">
            {displayWorkflows.length > 0 && (
              <StatusIndicator status={displayWorkflows[displayWorkflows.length - 1].status} />
            )}
          </p>
        ) : (
          <div className="flex flex-col mb-1 min-w-0">
            {displayWorkflows.map((workflowRun) => (
              <p key={workflowRun.id} className="text-sm pl-2">
                {getWorkflowTypeName(workflowRun.type)}: <StatusIndicator status={workflowRun.status} />
              </p>
            ))}
          </div>
        )}

        <p className="text-sm text-muted-foreground mt-1">
          Created {formatDistanceToNow(project.created_at, { addSuffix: true })}
        </p>
      </div>

      <div className="flex gap-2">
        {isToolRun ? (
          <Link href={`${toolInfo.route}?projectId=${project.id}`}>
            <Button variant="outline" size="sm">
              Open Tool <ChevronRightIcon className="w-4 h-4" />
            </Button>
          </Link>
        ) : (
          <Link href={`/projects/${project.id}`}>
            <Button variant="outline" size="sm">
              View Project <ChevronRightIcon className="w-4 h-4" />
            </Button>
          </Link>
        )}

        <DeleteProjectDialog projectId={project.id} projectTitle={project.title} />
      </div>
    </div>
  );
}
