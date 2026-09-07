/**
 * Model registry for the /chat page.
 *
 * This module is intentionally free of any AI SDK / component imports so it can
 * be shared between the client (model selector) and the server (`/api/chat`
 * route). Only the gpt-5.6 tier is offered; terra is the default because it is
 * the model every backend agent runs on (see `lib/config/llm_models.py`).
 */

export interface ChatModel {
  id: string;
  name: string;
}

export const CHAT_MODELS: ChatModel[] = [
  { id: 'gpt-5.6-terra', name: 'GPT-5.6 Terra' },
  { id: 'gpt-5.6-luna', name: 'GPT-5.6 Luna' },
  { id: 'gpt-5.6-sol', name: 'GPT-5.6 Sol' },
];

export const DEFAULT_MODEL_ID = 'gpt-5.6-terra';

export function getChatModel(id: string): ChatModel | undefined {
  return CHAT_MODELS.find((model) => model.id === id);
}
