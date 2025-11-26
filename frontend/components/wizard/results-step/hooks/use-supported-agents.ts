import { healthApi } from '@/lib/api';
import { AgentInfo } from '@/lib/generated-api';
import { useQuery } from '@tanstack/react-query';

interface UseSupportedAgentsReturn {
  supportedAgents: AgentInfo[] | undefined;
  supportedAgentsError: string | null;
  isLoading: boolean;
}

export function useSupportedAgents(): UseSupportedAgentsReturn {
  const {
    data: supportedAgents,
    isLoading,
    error: supportedAgentsError,
  } = useQuery({
    queryKey: ['supportedAgents'],
    staleTime: Infinity,
    queryFn: () => healthApi.getSupportedAgentsApiSupportedAgentsGet(),
  });

  return {
    supportedAgents,
    supportedAgentsError: supportedAgentsError?.message || null,
    isLoading,
  };
}
