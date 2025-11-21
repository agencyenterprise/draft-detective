'use client';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { analysisService } from '@/lib/analysis-service';
import { ChunkReevaluationRequest, ClaimSubstantiatorStateOutput } from '@/lib/generated-api';
import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import * as React from 'react';
import { useAgentSelection } from '../hooks/use-agent-selection';
import { useSupportedAgents } from '../hooks/use-supported-agents';
import { AgentSelector } from './agent-selector';

interface ChunkReevaluateControlProps {
  chunkIndex: number;
  originalState: ClaimSubstantiatorStateOutput;
  sessionId?: string | null;
  workflowRunId: string;
}

export function ChunkReevaluateControl({
  chunkIndex,
  originalState,
  sessionId,
  workflowRunId,
}: ChunkReevaluateControlProps) {
  const [isDialogOpen, setIsDialogOpen] = React.useState(false);
  const { supportedAgents, supportedAgentsError } = useSupportedAgents();
  const agentSelection = useAgentSelection({ supportedAgents, supportedAgentsError });
  const [openaiApiKey, setOpenaiApiKey] = useSessionStorage<string>('openai-api-key', '');
  const hideOpenaiApiKeyInput = process.env.NEXT_PUBLIC_HIDE_CUSTOM_OPENAI_API_KEY_INPUT === 'true';
  const queryClient = useQueryClient();

  const reevaluateMutation = useMutation({
    mutationFn: async (request: ChunkReevaluationRequest) => {
      return await analysisService.reevaluateChunk(request);
    },
    onMutate: () => {
      // Close dialog immediately
      setIsDialogOpen(false);
      agentSelection.setError(null);

      // Invalidate queries to show loading state
      queryClient.refetchQueries({
        queryKey: ['chunkDetails', workflowRunId, chunkIndex],
      });
      queryClient.refetchQueries({
        queryKey: ['workflowRun', workflowRunId],
      });
    },
    onError: (error) => {
      console.error('Re-evaluation failed:', error);
      // Re-open dialog on error to show the error message
      setIsDialogOpen(true);
      agentSelection.setError(error instanceof Error ? error.message : 'Re-evaluation failed');
    },
  });

  const handleReevaluate = () => {
    if (!agentSelection.validateSelection()) {
      return;
    }

    if (!hideOpenaiApiKeyInput && (!openaiApiKey || openaiApiKey.trim() === '')) {
      agentSelection.setError('OpenAI API key is required');
      return;
    }

    const request: ChunkReevaluationRequest = {
      chunkIndex: chunkIndex,
      agentsToRun: Array.from(agentSelection.selectedAgents),
      originalState: originalState,
      sessionId: sessionId ?? null,
      openaiApiKey: hideOpenaiApiKeyInput ? null : openaiApiKey,
    };

    reevaluateMutation.mutate(request);
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
          <DialogContent className="min-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Re-evaluate Chunk {chunkIndex}</DialogTitle>
              <DialogDescription>
                {hideOpenaiApiKeyInput
                  ? 'Select the agents to run to re-analyze this chunk.'
                  : 'Select the agents to run and provide your OpenAI API key to re-analyze this chunk.'}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-6">
              {!hideOpenaiApiKeyInput && (
                <div className="space-y-2">
                  <Label htmlFor="reevaluate-openai-key" required>
                    OpenAI API Key
                  </Label>
                  <Input
                    id="reevaluate-openai-key"
                    type="text"
                    placeholder="sk-..."
                    value={openaiApiKey}
                    onChange={(e) => setOpenaiApiKey(e.target.value)}
                    disabled={isReevaluating}
                    error={!openaiApiKey || openaiApiKey.trim() === ''}
                  />
                  <p className="text-xs text-muted-foreground">
                    Your OpenAI API key will be used only for this re-evaluation and will not be stored in our database.
                  </p>
                </div>
              )}

              <div className="space-y-4">
                <AgentSelector
                  supportedAgents={supportedAgents}
                  supportedAgentsError={supportedAgentsError}
                  selectedAgents={agentSelection.selectedAgents}
                  onAgentToggle={agentSelection.handleAgentToggle}
                  onSelectAll={agentSelection.handleSelectAll}
                  onDeselectAll={agentSelection.handleDeselectAll}
                  disabled={isReevaluating}
                  title="Select Agents to Run:"
                />
              </div>

              {agentSelection.error && (
                <div className="text-sm text-red-600 bg-red-50 p-2 rounded">{agentSelection.error}</div>
              )}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setIsDialogOpen(false)} disabled={isReevaluating}>
                Cancel
              </Button>
              <Button
                onClick={handleReevaluate}
                disabled={
                  isReevaluating ||
                  agentSelection.selectedAgents.size === 0 ||
                  (!hideOpenaiApiKeyInput && !openaiApiKey?.trim())
                }
              >
                {isReevaluating ? 'Re-analyzing...' : 'Run Re-analysis'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
