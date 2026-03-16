import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowRight, Brain, ChevronRight, FlaskConical, Github } from 'lucide-react';
import Link from 'next/link';

const mockProjects = [
  {
    id: 'demo-1',
    title: 'Vitamin D Supplementation Literature Review',
    status: 'Completed',
    claims: 18,
    citations: 26,
    created: '2 days ago',
  },
  {
    id: 'demo-2',
    title: 'FDA Guidance on AI/ML Medical Devices',
    status: 'Completed',
    claims: 24,
    citations: 41,
    created: '5 days ago',
  },
  {
    id: 'demo-3',
    title: 'Climate Impact Assessment 2024',
    status: 'Processing',
    claims: null,
    citations: null,
    created: '1 hour ago',
  },
];

export default function OriginalHome() {
  return (
    <div className="container mx-auto max-w-6xl space-y-16 px-4 py-4">
      <div className="space-y-6 text-center">
        <div className="space-y-4">
          <Badge variant="secondary" className="text-sm">
            <Brain className="mr-1 h-3 w-3" />
            AI-Powered Peer Review
          </Badge>
          <h1 className="bg-gradient-to-r from-foreground via-foreground/90 to-foreground/70 bg-clip-text text-5xl font-bold text-transparent md:text-6xl">
            AI Reviewer
          </h1>
          <p className="mx-auto max-w-3xl text-lg leading-relaxed text-muted-foreground">
            Transform your document review process with AI-powered claim extraction, citation analysis, and evidence
            substantiation. Built for researchers, analysts, and content reviewers who demand accuracy and thoroughness.
          </p>
        </div>

        <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link href="/original">
            <Button size="lg">
              <FlaskConical className="h-5 w-5" />
              Start a Project
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
          <Link href="https://github.com/agencyenterprise/ai-reviewer" target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="lg">
              <Github className="h-5 w-5" />
              View on GitHub
            </Button>
          </Link>
        </div>
      </div>

      <div className="space-y-6">
        <h2 className="text-2xl font-bold">Your Projects</h2>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {mockProjects.map((project) => (
            <Link key={project.id} href={`/original/${project.id}`}>
              <Card className="h-full transition-shadow hover:shadow-lg">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <Badge variant={project.status === 'Completed' ? 'default' : 'secondary'}>{project.status}</Badge>
                    <span className="text-sm text-muted-foreground">{project.created}</span>
                  </div>
                  <CardTitle className="text-lg">{project.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <div className="space-y-1 text-sm text-muted-foreground">
                      <p>{project.claims !== null ? `${project.claims} claims` : 'Processing...'}</p>
                      <p>{project.citations !== null ? `${project.citations} citations` : 'Processing...'}</p>
                    </div>
                    <ChevronRight className="h-5 w-5 text-muted-foreground" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
