'use client';

import { AnalysisForm } from '@/components/analysis-form';

export default function New() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted">
      <div className="container mx-auto px-4 py-12 max-w-6xl">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-center mb-4 bg-gradient-to-r from-foreground to-foreground/80 bg-clip-text text-transparent">
            AI Reviewer
          </h1>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Upload your documents and configure your analysis settings to receive a comprehensive review.
          </p>
        </div>

        <div className="bg-background backdrop-blur-sm border border-border/50 rounded-2xl p-8 shadow-sm">
          <AnalysisForm />
        </div>
      </div>
    </div>
  );
}
