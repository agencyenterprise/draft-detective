import { ProjectsList } from '@/components/projects-list';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ArrowRight, Brain, FlaskConical } from 'lucide-react';
import Link from 'next/link';

export default function Home() {
  return (
    <div className="container mx-auto px-4 py-4 max-w-6xl space-y-16">
      <div className="text-center space-y-6">
        <div className="space-y-4">
          <Badge variant="secondary" className="text-sm">
            <Brain className="w-3 h-3 mr-1" />
            AI-Powered Peer Review
          </Badge>
          <h1 className="text-5xl md:text-6xl font-bold bg-gradient-to-r from-foreground via-foreground/90 to-foreground/70 bg-clip-text text-transparent">
            Draft Detective
          </h1>
          <p className="text-lg text-muted-foreground max-w-3xl mx-auto leading-relaxed">
            Transform your document review process with Draft Detective. Run pre-peer review checks on your manuscript
            and get a prioritized list of flagged issues. Built for researchers, analysts, and content reviewers who
            want to catch problems before reviewers do.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center items-center">
          <Link href="/new">
            <Button size="lg">
              <FlaskConical className="w-5 h-5" />
              Start a Project
              <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
        </div>
      </div>

      <ProjectsList />
    </div>
  );
}
