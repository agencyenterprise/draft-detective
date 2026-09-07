import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { listChatModelsApiChatModelsGet, listChatSkillsApiChatSkillsGet } from '@/lib/generated-api';

export const CHAT_MODELS_QUERY_KEY = ['chat', 'models'] as const;
export const CHAT_SKILLS_QUERY_KEY = ['chat', 'skills'] as const;

// Both lists change only with a deploy, so a long cache is right.
const ONE_HOUR = 60 * 60 * 1000;

/** The models the chat page may offer, as the backend allows them. */
export function useChatModels() {
  const session = useSession();
  return useQuery({
    enabled: session.status === 'authenticated',
    queryKey: CHAT_MODELS_QUERY_KEY,
    queryFn: () => listChatModelsApiChatModelsGet(),
    staleTime: ONE_HOUR,
  });
}

/** The skills offered as slash commands, read from the repo's `skills/` on the backend. */
export function useChatSkills() {
  const session = useSession();
  return useQuery({
    enabled: session.status === 'authenticated',
    queryKey: CHAT_SKILLS_QUERY_KEY,
    queryFn: () => listChatSkillsApiChatSkillsGet(),
    staleTime: ONE_HOUR,
  });
}
