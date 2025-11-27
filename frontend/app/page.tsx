import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ProjectsList } from '@/components/projects-list';
import { ArrowRight, Brain, FlaskConical, TestTube } from 'lucide-react';
import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted">
      <div className="container mx-auto px-4 py-12 max-w-6xl space-y-16">
        <div className="text-center space-y-6">
          <div className="space-y-4">
            <Badge variant="secondary" className="text-sm">
              <Brain className="w-3 h-3 mr-1" />
              AI-Powered Peer Review
            </Badge>
            <h1 className="text-5xl md:text-6xl font-bold bg-gradient-to-r from-foreground via-foreground/90 to-foreground/70 bg-clip-text text-transparent">
              AI Reviewer
            </h1>
            <p className="text-lg text-muted-foreground max-w-3xl mx-auto leading-relaxed">
              Transform your document review process with AI-powered claim extraction, citation analysis, and evidence
              substantiation. Built for researchers, analysts, and content reviewers who demand accuracy and
              thoroughness.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Link href="/new">
              <Button size="lg">
                <FlaskConical className="w-5 h-5" />
                Start Analysis
                <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
            <Link href="/evals">
              <Button size="lg" variant="outline">
                <TestTube className="w-5 h-5" />
                View Evaluations
              </Button>
            </Link>
          </div>
        </div>

        <ProjectsList />
      </div>
    </div>
  );
}
