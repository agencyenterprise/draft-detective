import { useMemo } from 'react';
import { useChatSkills } from '@/lib/hooks/use-chat-catalog';

export interface SkillCommand {
  /** Skill name — used as the slash-command id / trigger. */
  id: string;
  /** Description shown in the slash-command menu. */
  description: string;
}

/**
 * One slash command per skill the backend offers; empty until the list has
 * loaded. Descriptions come from `GET /api/chat/skills`, which prefers the
 * related workflow's manifest description and falls back to the SKILL.md one.
 */
export function useSkillCommands(): SkillCommand[] {
  const { data: skills } = useChatSkills();
  return useMemo(() => (skills ?? []).map((skill) => ({ id: skill.name, description: skill.description })), [skills]);
}
