'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { detectToolFromWorkflows, ToolDefinition } from '@/lib/tool-registry';
import { ProjectTypeFilter, ProjectTypeValue } from '@/components/projects/project-type-filter';
import { ProjectCard } from '@/components/projects/project-card';
import { useQuery } from '@tanstack/react-query';
import { PlusIcon } from 'lucide-react';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import { listProjectsEndpointApiProjectsGet, ProjectListItem } from '@/lib/generated-api';

interface ProjectsListProps {
  className?: string;
}

type ProjectWithToolInfo = ProjectListItem & {
  toolInfo: ToolDefinition | null;
};

export function ProjectsList({ className }: ProjectsListProps) {
  const session = useSession();
  const [typeFilter, setTypeFilter] = useState<ProjectTypeValue[]>(['projects']);

  const {
    data: projects,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['projects'],
    enabled: !!session.data?.user,
    refetchInterval: 3000,
    queryFn: () => listProjectsEndpointApiProjectsGet(),
  });

  const projectsWithToolInfo = useMemo<ProjectWithToolInfo[]>(() => {
    return (
      projects?.map((item) => ({
        ...item,
        toolInfo: detectToolFromWorkflows(item.workflow_runs?.map((w) => w.type) || []),
      })) || []
    );
  }, [projects]);

  const filteredProjects = useMemo(() => {
    const showProjects = typeFilter.includes('projects');
    const showToolRuns = typeFilter.includes('tool-runs');

    return projectsWithToolInfo.filter((p) => {
      const isTool = p.toolInfo !== null;
      return (showProjects && !isTool) || (showToolRuns && isTool);
    });
  }, [projectsWithToolInfo, typeFilter]);

  if (!session.data?.user) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>My projects</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 space-y-4">
            <p className="text-muted-foreground">Please sign in to view your projects</p>
            <Button variant="outline" asChild>
              <Link href="/api/auth/signin">Sign in</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>My projects</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
            <p className="mt-2 text-muted-foreground">Loading your projects...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>My projects</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <p className="text-destructive">{error.message}</p>
            <Button variant="outline" onClick={() => window.location.reload()} className="mt-2">
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (projectsWithToolInfo.length === 0) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>My projects</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center space-y-6">
            <div className="space-y-1">
              <p className="text-muted-foreground">You don&apos;t have any projects yet</p>
              <p className="text-sm text-muted-foreground">Start a new project or use our standalone tools</p>
            </div>
            <div className="flex gap-2 justify-center">
              <Button variant="outline" asChild>
                <Link href="/new">
                  <PlusIcon className="w-5 h-5" /> New Project
                </Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href="/tools">View Tools</Link>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Your Projects</CardTitle>
            <p className="text-sm text-muted-foreground">
              {filteredProjects.length} of {projectsWithToolInfo.length}
            </p>
          </div>
          <ProjectTypeFilter value={typeFilter} onChange={setTypeFilter} />
        </div>
      </CardHeader>
      <CardContent>
        {filteredProjects.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <p>
              No {typeFilter.includes('projects') && !typeFilter.includes('tool-runs') ? 'projects' : 'tool runs'}{' '}
              found.
            </p>
            <Button
              variant="link"
              onClick={() => {
                if (typeFilter.includes('projects') && !typeFilter.includes('tool-runs')) {
                  setTypeFilter(['tool-runs']);
                } else {
                  setTypeFilter(['projects']);
                }
              }}
              className="mt-2"
            >
              Show {typeFilter.includes('projects') && !typeFilter.includes('tool-runs') ? 'tool runs' : 'projects'}
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredProjects.map((item) => (
              <ProjectCard key={item.project.id} item={item} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
