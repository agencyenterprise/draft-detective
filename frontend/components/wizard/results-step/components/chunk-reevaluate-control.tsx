import { Button } from '@/components/ui/button';
import { Dialog, DialogTrigger } from '@/components/ui/dialog';
import { analysisApi } from '@/lib/api';
import { ClaimSubstantiatorStateSummary, RerunAnalysisRequest } from '@/lib/generated-api';
import { useMutation } from '@tanstack/react-query';
import * as React from 'react';
import { toast } from 'sonner';
import { ReevaluationDialogContent, ReevaluationFormValues } from './reevaluation-dialog-content';

interface ChunkReevaluateControlProps {
  chunkIndex: number;
  results: ClaimSubstantiatorStateSummary;
  workflowRunId: string;
}

export function ChunkReevaluateControl({ results, chunkIndex, workflowRunId }: ChunkReevaluateControlProps) {
  const [isDialogOpen, setIsDialogOpen] = React.useState(false);

  const reevaluateMutation = useMutation({
    mutationFn: async (request: RerunAnalysisRequest) => {
      return await analysisApi.rerunAnalysisEndpointApiRerunAnalysisPost({
        rerunAnalysisRequest: request,
      });
    },
    onSuccess: (_data, variables, _context, { client }) => {
      setIsDialogOpen(false);

      // Invalidate queries to show loading state
      client.invalidateQueries({
        queryKey: ['chunkDetails', variables.workflowRunId, chunkIndex],
        refetchType: 'all',
      });
      client.invalidateQueries({
        queryKey: ['workflowRun', variables.workflowRunId],
      });
    },
    onError: (error) => {
      console.error('Re-evaluation failed:', error);
      toast.error(error instanceof Error ? error.message : 'Re-evaluation failed');
    },
  });

  const handleReevaluate = (values: ReevaluationFormValues) => {
    reevaluateMutation.mutate({
      workflowRunId,
      config: {
        ...results.config,
        targetChunkIndices: [chunkIndex],
        agentsToRun: values.selectedAgents,
        openaiApiKey: values.openaiApiKey,
      },
    });
  };

  const isReevaluating = reevaluateMutation.isPending;

  return (
    <div className="border-t pt-3 mt-3">
      <div className="flex items-center justify-between">
        <h5 className="text-sm font-medium text-gray-700">Re-evaluate Chunk</h5>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm" disabled={isReevaluating}>
              Re-analyze
            </Button>
          </DialogTrigger>
          <ReevaluationDialogContent
            chunkIndex={chunkIndex}
            isPending={isReevaluating}
            onCancel={() => setIsDialogOpen(false)}
            onConfirm={handleReevaluate}
          />
        </Dialog>
      </div>
    </div>
  );
}
