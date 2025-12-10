import * as React from 'react';
import { AgentInfo } from '@/lib/generated-api';

interface UseAgentSelectionProps {
  supportedAgents: AgentInfo[] | undefined;
  supportedAgentsError: string | null;
}

export function useAgentSelection({ supportedAgents, supportedAgentsError }: UseAgentSelectionProps) {
  const [selectedAgents, setSelectedAgents] = React.useState<Set<string>>(new Set());
  const [error, setError] = React.useState<string | null>(null);

  // Initialize with all agents selected when supportedAgents loads
  React.useEffect(() => {
    if (supportedAgents) {
      setSelectedAgents((selectedAgents) =>
        !selectedAgents.size ? new Set(supportedAgents.map((agent) => agent.function_name)) : selectedAgents,
      );
    }
  }, [supportedAgents]);

  // Update error state when supportedAgentsError changes
  React.useEffect(() => {
    if (supportedAgentsError) {
      setError(supportedAgentsError);
    }
  }, [supportedAgentsError]);

  const handleAgentToggle = (agent: AgentInfo, checked: boolean) => {
    const newSelected = new Set(selectedAgents);
    if (checked) {
      newSelected.add(agent.function_name);
    } else {
      newSelected.delete(agent.function_name);
    }
    setSelectedAgents(newSelected);
  };

  const handleSelectAll = () => {
    if (supportedAgents) {
      setSelectedAgents(new Set(supportedAgents.map((agent) => agent.function_name)));
    }
  };

  const handleDeselectAll = () => {
    setSelectedAgents(new Set());
  };

  const validateSelection = (customErrorMessage?: string): boolean => {
    if (selectedAgents.size === 0) {
      setError(customErrorMessage || 'Please select at least one agent');
      return false;
    }
    setError(null);
    return true;
  };

  return {
    selectedAgents,
    error,
    setError,
    handleAgentToggle,
    handleSelectAll,
    handleDeselectAll,
    validateSelection,
  };
}
