'use client';

import type { FC, ReactNode } from 'react';
import { ClaudeLogo, GeminiLogo, OpenAILogo } from '@/components/assistant-ui/logos';
import { ModelSelector, type ModelOption } from '@/components/assistant-ui/model-selector';
import { useChatModels } from '@/lib/hooks/use-chat-catalog';

/** The provider logo for a model id, by the id's well-known prefix. */
function logoFor(modelId: string): ReactNode {
  const id = modelId.toLowerCase();
  if (id.startsWith('gpt') || id.startsWith('o')) return <OpenAILogo className="size-4" />;
  if (id.startsWith('claude')) return <ClaudeLogo className="size-4" />;
  if (id.startsWith('gemini')) return <GeminiLogo className="size-4" />;
  return undefined;
}

/**
 * Model picker for the chat composer. The list and its default come from the
 * backend allowlist (`GET /api/chat/models`); the chosen id is registered into
 * assistant-ui's ModelContext and reaches the chat adapter as
 * `context.config.modelName`. Until the list has loaded nothing is rendered and
 * the backend answers with its default model.
 */
export const ChatModelSelector: FC = () => {
  const { data: models } = useChatModels();
  if (!models?.length) return null;

  const options: ModelOption[] = models.map((model) => ({
    id: model.id,
    name: model.name,
    icon: logoFor(model.id),
  }));
  const defaultValue = models.find((model) => model.is_default)?.id ?? models[0].id;

  return <ModelSelector models={options} defaultValue={defaultValue} variant="ghost" align="start" />;
};
