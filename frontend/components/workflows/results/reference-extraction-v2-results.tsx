'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ReferenceExtractionV2State, WorkflowRunDetail } from '@/lib/generated-api';
import { AlertCircle, BookOpen, Brain, ChevronDown } from 'lucide-react';
import { useState } from 'react';

interface ReferenceExtractionV2ResultsProps {
  workflowDetail: WorkflowRunDetail;
}

export function ReferenceExtractionV2Results({ workflowDetail }: ReferenceExtractionV2ResultsProps) {
  const state = workflowDetail.state as ReferenceExtractionV2State | undefined;
  const references = state?.references ?? [];
  const reasoning = state?.reasoning;
  const [isReasoningOpen, setIsReasoningOpen] = useState(false);

  if (references.length === 0) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <div className="text-center space-y-2">
            <AlertCircle className="h-8 w-8 text-muted-foreground mx-auto" />
            <p className="text-sm text-muted-foreground">No references extracted yet.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {reasoning && (
        <Card>
          <CardContent className="py-3">
            <Button
              variant="ghost"
              className="w-full justify-start p-0 h-auto hover:bg-transparent"
              onClick={() => setIsReasoningOpen(!isReasoningOpen)}
            >
              <Brain className="h-4 w-4 text-purple-600 mr-2" />
              <span className="text-sm font-medium">Agent Reasoning</span>
              <ChevronDown
                className={`h-4 w-4 ml-auto text-muted-foreground transition-transform ${isReasoningOpen ? 'rotate-180' : ''}`}
              />
            </Button>
            {isReasoningOpen && (
              <p className="text-sm text-muted-foreground whitespace-pre-wrap mt-3 pt-3 border-t">{reasoning}</p>
            )}
          </CardContent>
        </Card>
      )}

      <div className="flex items-center gap-2">
        <BookOpen className="h-5 w-5 text-blue-600" />
        <span className="text-sm font-medium">Extracted References</span>
        <Badge variant="secondary" className="ml-auto">
          {references.length} Reference{references.length !== 1 ? 's' : ''}
        </Badge>
      </div>

      <div className="space-y-2">
        {references.map((reference, index) => (
          <Card key={index}>
            <CardContent>
              <div className="flex items-start gap-3">
                <span className="text-xs font-medium text-muted-foreground bg-muted px-2 py-1 rounded shrink-0">
                  {index + 1}
                </span>
                <p className="text-sm leading-relaxed">{reference}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
