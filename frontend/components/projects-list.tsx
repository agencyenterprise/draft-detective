'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ProjectCard } from '@/components/projects/project-card';
import { useQuery } from '@tanstack/react-query';
import { PlusIcon } from 'lucide-react';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { listProjectsEndpointApiProjectsGet } from '@/lib/generated-api';

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
    queryFn: () => listProjectsEndpointApiProjectsGet(),
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

  if (!projects || projects.length === 0) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>My projects</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center space-y-6">
            <p className="text-muted-foreground">You don&apos;t have any projects yet</p>
            <Button variant="outline" asChild>
              <Link href="/new">
                <PlusIcon className="w-5 h-5" /> New Project
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
        <p className="text-sm text-muted-foreground">{projects.length} projects</p>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {projects.map((item) => (
            <ProjectCard key={item.project.id} item={item} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
