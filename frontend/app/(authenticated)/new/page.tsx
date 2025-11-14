'use client';

import { AnalysisForm } from '@/components/analysis-form';

export default function New() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold">Start a new analysis</h1>
        <p className="text-muted-foreground text-sm">
          Upload your documents and configure your analysis settings to receive a comprehensive review.
        </p>
      </div>

      <div className="bg-background backdrop-blur-sm border border-border/50 rounded-2xl p-8 shadow-sm">
        <AnalysisForm />
      </div>
    </div>
  );
}
