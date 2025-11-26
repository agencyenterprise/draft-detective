'use client';

import * as React from 'react';
import { Button } from '@/components/ui/button';
import { AgentInfo } from '@/lib/generated-api';
import { AgentSelector } from './agent-selector';
import { useAgentSelection } from '../hooks/use-agent-selection';

interface ExpandableControlProps {
  title: string;
  buttonText: React.ReactNode;
  expandedButtonText: string;
  isProcessing: boolean;
  processingText: string;
  chunkIndex: number;
  supportedAgents: AgentInfo[] | undefined;
  supportedAgentsError: string | null;
  agentSelectorTitle: string;
  backgroundClassName?: string;
  footerText: string;
  actionButtonText: string;
  onAction: (selectedAgents: Set<string>) => Promise<void>;
  children?: (selectedAgents: Set<string>) => React.ReactNode;
}

export function ExpandableControl({
  title,
  buttonText,
  isProcessing,
  processingText,
  chunkIndex,
  supportedAgents,
  supportedAgentsError,
  agentSelectorTitle,
  backgroundClassName = 'bg-gray-50',
  footerText,
  actionButtonText,
  onAction,
  children,
}: ExpandableControlProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const agentSelection = useAgentSelection({ supportedAgents, supportedAgentsError });

  const handleAction = async () => {
    if (!agentSelection.validateSelection()) {
      return;
    }

    try {
      await onAction(agentSelection.selectedAgents);
      setIsExpanded(false);
    } catch (error) {
      console.error('Action failed:', error);
      agentSelection.setError(error instanceof Error ? error.message : 'Action failed');
    }
  };

  if (supportedAgentsError) {
    return <div className="text-sm text-red-500">Error: {supportedAgentsError}</div>;
  }

  if (!supportedAgents) {
    return <div className="text-sm text-gray-500">Loading options...</div>;
  }

  return (
    <div className="border-t pt-3 mt-3">
      <div className="flex items-center justify-between">
        <h5 className="text-sm font-medium text-gray-700">{title}</h5>
        <Button variant="outline" size="sm" onClick={() => setIsExpanded(!isExpanded)} disabled={isProcessing}>
          {isExpanded ? 'Cancel' : buttonText}
        </Button>
      </div>

      {isExpanded && (
        <div className={`mt-3 p-3 ${backgroundClassName} rounded-md space-y-3`}>
          <AgentSelector
            supportedAgents={supportedAgents}
            supportedAgentsError={supportedAgentsError}
            selectedAgents={agentSelection.selectedAgents}
            onAgentToggle={agentSelection.handleAgentToggle}
            onSelectAll={agentSelection.handleSelectAll}
            onDeselectAll={agentSelection.handleDeselectAll}
            disabled={isProcessing}
            title={agentSelectorTitle}
          />

          {children && children(agentSelection.selectedAgents)}

          {agentSelection.error && (
            <div className="text-sm text-red-600 bg-red-50 p-2 rounded">{agentSelection.error}</div>
          )}

          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">{footerText.replace('{chunkIndex}', chunkIndex.toString())}</span>
            <Button
              onClick={handleAction}
              disabled={isProcessing || agentSelection.selectedAgents.size === 0}
              size="sm"
            >
              {isProcessing ? processingText : actionButtonText}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
