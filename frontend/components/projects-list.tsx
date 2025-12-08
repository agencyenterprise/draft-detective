'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { StatusIndicator } from '@/components/ui/status-indicator';
import { projectsApi } from '@/lib/api';
import { getWorkflowTypeName } from '@/lib/workflow-state';
import { useQuery } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { ChevronRightIcon, PlusIcon } from 'lucide-react';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { DeleteProjectDialog } from './delete-project-dialog';

interface ProjectsListProps {
  className?: string;
}

export function ProjectsList({ className }: ProjectsListProps) {
  const session = useSession();

  const {
    data: projects,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['projects'],
    enabled: !!session.data?.user,
    refetchInterval: 3000,
    queryFn: () => projectsApi.listProjectsEndpointApiProjectsGet(),
  });

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

  if (projects?.length === 0) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>My projects</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center space-y-6">
            <div className="space-y-1">
              <p className="text-muted-foreground">You don&apos;t have any projects yet</p>
              <p className="text-sm text-muted-foreground">
                Start a new project to <strong>upload your documents</strong> and <strong>analyze them</strong> or to
                start a new <strong>research project</strong>.
              </p>
            </div>
            <Button variant="outline" asChild>
              <Link href="/new">
                <PlusIcon className="w-5 h-5" /> Start a new project
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Your Projects</CardTitle>
        <p className="text-sm text-muted-foreground">
          Projects are private and only you can access them, unless explicitly shared with others.
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {projects?.map(({ project, workflowRuns }) => (
            <div
              key={project.id}
              className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <div className="flex flex-col mb-1 min-w-0">
                  <h3 className="font-medium truncate">{project.title}</h3>
                  {workflowRuns?.map((workflowRun) => (
                    <p key={workflowRun.id} className="text-sm pl-2">
                      {getWorkflowTypeName(workflowRun.type)}: <StatusIndicator status={workflowRun.status} />
                    </p>
                  ))}
                </div>

                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <p>Project created {formatDistanceToNow(project.createdAt, { addSuffix: true })}</p>
                </div>
              </div>

              <div className="flex gap-2">
                <Link href={`/projects/${project.id}`}>
                  <Button variant="outline" size="sm">
                    View project <ChevronRightIcon className="w-4 h-4" />
                  </Button>
                </Link>

                <DeleteProjectDialog projectId={project.id} projectTitle={project.title} />
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
