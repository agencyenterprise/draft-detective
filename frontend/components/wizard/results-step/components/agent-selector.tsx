import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { AgentInfo } from '@/lib/generated-api';

interface AgentSelectorProps {
  supportedAgents: AgentInfo[] | undefined;
  supportedAgentsError: string | null;
  selectedAgents: Set<string>;
  onAgentToggle: (agent: AgentInfo, checked: boolean) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  disabled?: boolean;
  title?: string;
}

interface AgentCheckboxProps {
  agent: AgentInfo;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}

function AgentCheckbox({ agent, checked, disabled, onChange }: AgentCheckboxProps) {
  return (
    <label className="flex items-center space-x-2 cursor-pointer">
      <Checkbox checked={checked} disabled={disabled} onCheckedChange={onChange} />
      <div className="flex-1">
        <p className="text-sm font-medium">
          {agent.name} <span className="text-xs text-gray-500 font-normal font-mono">({agent.function_name})</span>
        </p>
        <p className="text-xs text-gray-500">{agent.description}</p>
      </div>
    </label>
  );
}

export function AgentSelector({
  supportedAgents,
  supportedAgentsError,
  selectedAgents,
  onAgentToggle,
  onSelectAll,
  onDeselectAll,
  disabled = false,
  title = 'Select Agents:',
}: AgentSelectorProps) {
  if (supportedAgentsError) {
    return <div className="text-sm text-red-500">Error: {supportedAgentsError}</div>;
  }

  if (!supportedAgents) {
    return <div className="text-sm text-gray-500">Loading agents...</div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium">{title}</span>
        <div className="space-x-2">
          <Button variant="ghost" size="sm" onClick={onSelectAll} className="text-xs h-6 px-2" disabled={disabled}>
            All
          </Button>
          <Button variant="ghost" size="sm" onClick={onDeselectAll} className="text-xs h-6 px-2" disabled={disabled}>
            None
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        {supportedAgents.map((agent) => (
          <AgentCheckbox
            key={agent.function_name}
            agent={agent}
            checked={selectedAgents.has(agent.function_name)}
            disabled={disabled}
            onChange={(checked) => onAgentToggle(agent, checked)}
          />
        ))}
      </div>

      <div className="mt-2">
        <span className="text-xs text-gray-500">
          {selectedAgents.size} of {supportedAgents.length} agents selected
        </span>
      </div>
    </div>
  );
}
